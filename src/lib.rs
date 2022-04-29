extern crate notify;
extern crate pyo3;

use std::collections::HashSet;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::thread::sleep;
use std::time::{Duration, SystemTime};

use pyo3::create_exception;
use pyo3::exceptions::{PyFileNotFoundError, PyRuntimeError, PyTypeError};
use pyo3::prelude::*;

use notify::event::{Event, EventKind, ModifyKind, RenameMode};
use notify::{PollWatcher, RecommendedWatcher, RecursiveMode, Result as NotifyResult, Watcher};

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

#[derive(Debug)]
enum WatcherEnum {
    Poll(PollWatcher),
    Recommended(RecommendedWatcher),
}

#[pyclass]
struct RustNotify {
    changes: Arc<Mutex<HashSet<(u8, String)>>>,
    error: Arc<Mutex<Option<String>>>,
    _watcher: WatcherEnum,
}

// macro to avoid duplicated code below
macro_rules! watcher_paths {
    ($watcher:ident, $paths:ident, $debug:ident) => {
        for watch_path in $paths.into_iter() {
            $watcher
                .watch(Path::new(&watch_path), RecursiveMode::Recursive)
                .map_err(|e| PyFileNotFoundError::new_err(format!("{}", e)))?;
        }
        if $debug {
            eprintln!("watcher: {:?}", $watcher);
        }
    };
}

#[pymethods]
impl RustNotify {
    #[new]
    fn py_new(watch_paths: Vec<String>, debug: bool, force_polling: bool, poll_delay_ms: u64) -> PyResult<Self> {
        let changes: Arc<Mutex<HashSet<(u8, String)>>> = Arc::new(Mutex::new(HashSet::<(u8, String)>::new()));
        let error: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));

        let changes_clone = changes.clone();
        let error_clone = error.clone();

        let event_handler = move |res: NotifyResult<Event>| match res {
            Ok(event) => {
                if debug {
                    eprintln!("raw-event: {:?}", event);
                }
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
                        _ => return,
                    };
                    changes_clone.lock().unwrap().insert((change, path));
                }
            }
            Err(e) => {
                *error_clone.lock().unwrap() = Some(format!("error in underlying watcher: {}", e));
            }
        };

        let py_error = |e| WatchfilesRustInternalError::new_err(format!("Error creating watcher: {}", e));

        let _watcher: WatcherEnum = match force_polling {
            true => {
                let delay = Duration::from_millis(poll_delay_ms);
                let mut watcher = PollWatcher::with_delay(event_handler, delay).map_err(py_error)?;
                watcher_paths!(watcher, watch_paths, debug);
                WatcherEnum::Poll(watcher)
            }
            false => {
                let mut watcher = RecommendedWatcher::new(event_handler).map_err(py_error)?;
                watcher_paths!(watcher, watch_paths, debug);
                WatcherEnum::Recommended(watcher)
            }
        };

        Ok(RustNotify {
            changes,
            error,
            _watcher,
        })
    }

    pub fn watch(
        &self,
        py: Python,
        debounce_ms: u64,
        step_ms: u64,
        timeout_ms: u64,
        stop_event: PyObject,
    ) -> PyResult<PyObject> {
        let stop_event_is_set: Option<&PyAny> = match stop_event.is_none(py) {
            true => None,
            false => {
                let event: &PyAny = stop_event.extract(py)?;
                let func: &PyAny = event.getattr("is_set")?.extract()?;
                if !func.is_callable() {
                    return Err(PyTypeError::new_err("'stop_event.is_set' must be callable".to_string()));
                }
                Some(func)
            }
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
                    self.clear();
                    return Ok("signal".to_object(py));
                }
            };

            if let Some(error) = self.error.lock().unwrap().as_ref() {
                self.clear();
                return Err(WatchfilesRustInternalError::new_err(error.clone()));
            }

            if let Some(is_set) = stop_event_is_set {
                if is_set.call0()?.is_true()? {
                    self.clear();
                    return Ok("stop".to_object(py));
                }
            }

            let size = self.changes.lock().unwrap().len();
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
                    self.clear();
                    return Ok("timeout".to_object(py));
                }
            }
        }
        let py_changes = self.changes.lock().unwrap().to_object(py);
        self.clear();
        Ok(py_changes)
    }

    fn clear(&self) {
        self.changes.lock().unwrap().clear();
    }
}

#[pymodule]
fn _rust_notify(py: Python, m: &PyModule) -> PyResult<()> {
    m.add(
        "WatchfilesRustInternalError",
        py.get_type::<WatchfilesRustInternalError>(),
    )?;
    m.add_class::<RustNotify>()?;
    Ok(())
}
