extern crate notify;
extern crate pyo3;

use std::collections::HashSet;
use std::io::ErrorKind as IOErrorKind;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::thread::sleep;
use std::time::{Duration, SystemTime};

use pyo3::exceptions::{PyFileNotFoundError, PyOSError, PyPermissionError, PyRuntimeError};
use pyo3::prelude::*;
use pyo3::{create_exception, intern};

use notify::event::{Event, EventKind, ModifyKind, RenameMode};
use notify::{
    Config as NotifyConfig, ErrorKind as NotifyErrorKind, PollWatcher, RecommendedWatcher, RecursiveMode,
    Result as NotifyResult, Watcher,
};

create_exception!(
    _rust_notify,
    WatchfilesRustInternalError,
    PyRuntimeError,
    "Internal or filesystem error."
);

// these need to match `watchfiles/main.py::Change`
const CHANGE_ADDED: u8 = 1;
const CHANGE_MODIFIED: u8 = 2;
const CHANGE_DELETED: u8 = 3;

#[allow(dead_code)]
#[derive(Debug)]
enum WatcherEnum {
    None,
    Poll(PollWatcher),
    Recommended(RecommendedWatcher),
}

#[pyclass]
struct RustNotify {
    changes: Arc<Mutex<HashSet<(u8, String)>>>,
    error: Arc<Mutex<Option<String>>>,
    debug: bool,
    watcher: WatcherEnum,
}

fn map_watch_error(error: notify::Error) -> PyErr {
    let err_string = error.to_string();
    match error.kind {
        NotifyErrorKind::PathNotFound => return PyFileNotFoundError::new_err(err_string),
        NotifyErrorKind::Generic(ref err) => {
            // on Windows, we get a Generic with this message when the path does not exist
            if err.as_str() == "Input watch path is neither a file nor a directory." {
                return PyFileNotFoundError::new_err(err_string);
            }
        }
        NotifyErrorKind::Io(ref io_error) => match io_error.kind() {
            IOErrorKind::NotFound => return PyFileNotFoundError::new_err(err_string),
            IOErrorKind::PermissionDenied => return PyPermissionError::new_err(err_string),
            _ => (),
        },
        _ => (),
    };
    PyOSError::new_err(format!("{} ({:?})", err_string, error))
}

// macro to avoid duplicated code below
macro_rules! watcher_paths {
    ($watcher:ident, $paths:ident, $debug:ident, $recursive:ident, $ignore_permission_denied:ident) => {
        let mode = if $recursive {
            RecursiveMode::Recursive
        } else {
            RecursiveMode::NonRecursive
        };
        for watch_path in $paths.into_iter() {
            let result = $watcher.watch(Path::new(&watch_path), mode);
            match result {
                Err(err) => {
                    let err = map_watch_error(err);
                    if !$ignore_permission_denied {
                        return Err(err);
                    }
                }
                _ => (),
            }
        }
        if $debug {
            eprintln!("watcher: {:?}", $watcher);
        }
    };
}

macro_rules! wf_error {
    ($msg:expr) => {
        Err(WatchfilesRustInternalError::new_err($msg))
    };

    ($msg:literal, $( $msg_args:expr ),+ ) => {
        Err(WatchfilesRustInternalError::new_err(format!($msg, $( $msg_args ),+)))
    };
}

#[pymethods]
impl RustNotify {
    #[new]
    fn py_new(
        watch_paths: Vec<String>,
        debug: bool,
        force_polling: bool,
        poll_delay_ms: u64,
        recursive: bool,
        ignore_permission_denied: bool,
    ) -> PyResult<Self> {
        let changes: Arc<Mutex<HashSet<(u8, String)>>> = Arc::new(Mutex::new(HashSet::<(u8, String)>::new()));
        let error: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));

        let changes_clone = changes.clone();
        let error_clone = error.clone();

        let event_handler = move |res: NotifyResult<Event>| match res {
            Ok(event) => {
                if let Some(path_buf) = event.paths.first() {
                    let path = match path_buf.to_str() {
                        Some(s) => s.to_string(),
                        None => {
                            let msg = format!("Unable to decode path {:?} to string", path_buf);
                            *error_clone.lock().unwrap() = Some(msg);
                            return;
                        }
                    };
                    let change = match event.kind {
                        EventKind::Create(_) => CHANGE_ADDED,
                        EventKind::Modify(ModifyKind::Metadata(_))
                        | EventKind::Modify(ModifyKind::Data(_))
                        | EventKind::Modify(ModifyKind::Other)
                        | EventKind::Modify(ModifyKind::Any) => {
                            // these events sometimes happen when creating files and deleting them, hence these checks
                            let changes = changes_clone.lock().unwrap();
                            if changes.contains(&(CHANGE_DELETED, path.clone()))
                                || changes.contains(&(CHANGE_ADDED, path.clone()))
                            {
                                // file was already deleted or file was added in this batch, ignore this event
                                return;
                            } else {
                                CHANGE_MODIFIED
                            }
                        }
                        EventKind::Modify(ModifyKind::Name(RenameMode::From)) => CHANGE_DELETED,
                        EventKind::Modify(ModifyKind::Name(RenameMode::To)) => CHANGE_ADDED,
                        // RenameMode::Both duplicates RenameMode::From & RenameMode::To
                        EventKind::Modify(ModifyKind::Name(RenameMode::Both)) => return,
                        EventKind::Modify(ModifyKind::Name(_)) => {
                            // On macOS the modify name event is triggered when a file is renamed,
                            // but no information about whether it's the src or dst path is available.
                            // Hence we have to check if the file exists instead.
                            if Path::new(&path).exists() {
                                CHANGE_ADDED
                            } else {
                                CHANGE_DELETED
                            }
                        }
                        EventKind::Remove(_) => CHANGE_DELETED,
                        event_kind => {
                            if debug {
                                eprintln!(
                                    "raw-event={:?} event.kind={:?} no change detected",
                                    event_kind, event_kind
                                );
                            }
                            return;
                        }
                    };
                    if debug {
                        eprintln!("raw-event={:?} change={:?}", event, change);
                    }
                    changes_clone.lock().unwrap().insert((change, path));
                } else if debug {
                    eprintln!("raw-event={:?} no paths found", event);
                }
            }
            Err(e) => {
                if debug {
                    eprintln!("raw-error={:?} error.kind={:?} error.paths={:?}", e, e.kind, e.paths);
                }
                // see https://github.com/samuelcolvin/watchfiles/issues/282
                // if we have IO errors from files not found, we return "file deleted", rather than the error
                if let NotifyErrorKind::Io(io_error) = &e.kind {
                    if io_error.kind() == IOErrorKind::NotFound {
                        changes_clone.lock().unwrap().extend(
                            e.paths
                                .iter()
                                .map(|p| (CHANGE_DELETED, p.to_string_lossy().to_string())),
                        );
                        return;
                    }
                }
                *error_clone.lock().unwrap() = Some(format!("error in underlying watcher: {}", e));
            }
        };
        macro_rules! create_poll_watcher {
            ($msg_template:literal) => {{
                if watch_paths.iter().any(|p| !Path::new(p).exists()) {
                    return Err(PyFileNotFoundError::new_err("No such file or directory"));
                }
                let delay = Duration::from_millis(poll_delay_ms);
                let config = NotifyConfig::default().with_poll_interval(delay);
                let mut watcher = match PollWatcher::new(event_handler, config) {
                    Ok(watcher) => watcher,
                    Err(e) => return wf_error!($msg_template, e),
                };
                watcher_paths!(watcher, watch_paths, debug, recursive, ignore_permission_denied);
                Ok(WatcherEnum::Poll(watcher))
            }};
        }

        let watcher: WatcherEnum = match force_polling {
            true => create_poll_watcher!("Error creating poll watcher: {}"),
            false => {
                match RecommendedWatcher::new(event_handler.clone(), NotifyConfig::default()) {
                    Ok(watcher) => {
                        let mut watcher = watcher;
                        watcher_paths!(watcher, watch_paths, debug, recursive, ignore_permission_denied);
                        Ok(WatcherEnum::Recommended(watcher))
                    }
                    Err(error) => {
                        match &error.kind {
                            NotifyErrorKind::Io(io_error) => {
                                if io_error.raw_os_error() == Some(38) {
                                    // see https://github.com/samuelcolvin/watchfiles/issues/167
                                    // we callback to PollWatcher
                                    if debug {
                                        eprintln!(
                                            "IO error using recommend watcher: {:?}, falling back to PollWatcher",
                                            io_error
                                        );
                                    }
                                    create_poll_watcher!("Error creating fallback poll watcher: {}")
                                } else {
                                    wf_error!("Error creating recommended watcher: {}", error)
                                }
                            }
                            _ => {
                                wf_error!("Error creating recommended watcher: {}", error)
                            }
                        }
                    }
                }
            }
        }?;

        Ok(RustNotify {
            changes,
            error,
            debug,
            watcher,
        })
    }

    fn watch(
        slf: &Bound<Self>,
        py: Python,
        debounce_ms: u64,
        step_ms: u64,
        timeout_ms: u64,
        stop_event: PyObject,
    ) -> PyResult<PyObject> {
        if matches!(slf.borrow().watcher, WatcherEnum::None) {
            return Err(PyRuntimeError::new_err("RustNotify watcher closed"));
        }
        let stop_event_is_set: Option<Bound<PyAny>> = match stop_event.is_none(py) {
            true => None,
            false => Some(stop_event.getattr(py, intern!(py, "is_set"))?.into_bound(py)),
        };

        let mut max_debounce_time: Option<SystemTime> = None;
        let step_time = Duration::from_millis(step_ms);
        let mut last_size: usize = 0;
        let max_timeout_time: Option<SystemTime> = match timeout_ms {
            0 => None,
            _ => Some(SystemTime::now() + Duration::from_millis(timeout_ms)),
        };
        loop {
            py.allow_threads(|| sleep(step_time));
            match py.check_signals() {
                Ok(_) => (),
                Err(_) => {
                    slf.borrow().clear();
                    return Ok(intern!(py, "signal").as_any().to_owned().unbind());
                }
            };

            if let Some(error) = slf.borrow().error.lock().unwrap().as_ref() {
                slf.borrow().clear();
                return wf_error!(error.clone());
            }

            if let Some(is_set) = &stop_event_is_set {
                if is_set.call0()?.is_truthy()? {
                    if slf.borrow().debug {
                        eprintln!("stop event set, stopping...");
                    }
                    slf.borrow().clear();
                    return Ok(intern!(py, "stop").as_any().to_owned().unbind());
                }
            }

            let size = slf.borrow().changes.lock().unwrap().len();
            if size > 0 {
                if size == last_size {
                    break;
                }
                last_size = size;

                let now = SystemTime::now();
                if let Some(max_time) = max_debounce_time {
                    if now > max_time {
                        break;
                    }
                } else {
                    max_debounce_time = Some(now + Duration::from_millis(debounce_ms));
                }
            } else if let Some(max_time) = max_timeout_time {
                if SystemTime::now() > max_time {
                    slf.borrow().clear();
                    return Ok(intern!(py, "timeout").as_any().to_owned().unbind());
                }
            }
        }
        let py_changes = {
            let borrowed = slf.borrow();
            let mut locked_changes = borrowed.changes.lock().unwrap();
            let py_changes = locked_changes.to_owned().into_pyobject(py)?.into_any().unbind();
            // Clear the changes while holding the lock
            locked_changes.clear();
            py_changes
        };
        Ok(py_changes)
    }

    /// https://github.com/PyO3/pyo3/issues/1205#issuecomment-1164096251 for advice on `__enter__`
    fn __enter__(slf: Py<Self>) -> Py<Self> {
        slf
    }

    fn close(&mut self) {
        self.watcher = WatcherEnum::None;
    }

    fn __exit__(&mut self, _exc_type: PyObject, _exc_value: PyObject, _traceback: PyObject) {
        self.close();
    }

    fn __repr__(&self) -> PyResult<String> {
        Ok(format!("RustNotify({:#?})", self.watcher))
    }
}

impl RustNotify {
    fn clear(&self) {
        self.changes.lock().unwrap().clear();
    }
}

#[pymodule(gil_used = false)]
fn _rust_notify(py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    let mut version = env!("CARGO_PKG_VERSION").to_string();
    // cargo uses "1.0-alpha1" etc. while python uses "1.0.0a1", this is not full compatibility,
    // but it's good enough for now
    // see https://docs.rs/semver/1.0.9/semver/struct.Version.html#method.parse for rust spec
    // see https://peps.python.org/pep-0440/ for python spec
    // it seems the dot after "alpha/beta" e.g. "-alpha.1" is not necessary, hence why this works
    version = version.replace("-alpha", "a").replace("-beta", "b");
    m.add("__version__", version)?;
    m.add(
        "WatchfilesRustInternalError",
        py.get_type::<WatchfilesRustInternalError>(),
    )?;
    m.add_class::<RustNotify>()?;
    Ok(())
}
