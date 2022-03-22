extern crate notify;
extern crate pyo3;

use std::collections::HashSet;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::sleep;
use std::time::{Duration, SystemTime};

use pyo3::create_exception;
use pyo3::exceptions::{PyFileNotFoundError, PyRuntimeError};
use pyo3::prelude::*;

use notify::event::{Event, EventKind, ModifyKind};
use notify::{recommended_watcher, RecommendedWatcher, RecursiveMode, Result as NotifyResult, Watcher};

create_exception!(
    _rust_notify,
    WatchgodRustInternalError,
    PyRuntimeError,
    "Internal or filesystem error."
);

// these need to match `watchgod/watcher.py::Change`
const CHANGE_ADDED: u8 = 1;
const CHANGE_MODIFIED: u8 = 2;
const CHANGE_DELETED: u8 = 3;

#[pyclass]
struct RustNotify {
    changes: Arc<Mutex<HashSet<(u8, String)>>>,
    error: Arc<Mutex<Option<String>>>,
    _watcher: RecommendedWatcher,
}

#[pymethods]
impl RustNotify {
    #[new]
    fn py_new(watch_paths: Vec<String>, debug: bool) -> PyResult<Self> {
        let changes: Arc<Mutex<HashSet<(u8, String)>>> = Arc::new(Mutex::new(HashSet::<(u8, String)>::new()));
        let error: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));

        let changes_clone = changes.clone();
        let error_clone = error.clone();
        let last_rename = AtomicBool::new(false);

        let mut _watcher: RecommendedWatcher = recommended_watcher(move |res: NotifyResult<Event>| match res {
            Ok(event) => {
                if debug {
                    println!("raw-event: {:?}", event);
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
                        EventKind::Modify(ModifyKind::Metadata(_)) | EventKind::Modify(ModifyKind::Data(_)) => {
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
                        EventKind::Modify(ModifyKind::Name(_)) => {
                            // this just alternates `last_rename` between true and false
                            if last_rename.fetch_xor(true, Ordering::SeqCst) {
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
                println!("error: {:?}", e);
                // *error_clone.lock().unwrap() = Some(format!("error in underlying watcher: {}", e));
            }
        })
        .map_err(|e| WatchgodRustInternalError::new_err(format!("Error creating watcher: {}", e)))?;

        for watch_path in watch_paths.into_iter() {
            _watcher
                .watch(Path::new(&watch_path), RecursiveMode::Recursive)
                .map_err(|e| PyFileNotFoundError::new_err(format!("{}", e)))?;
        }

        Ok(RustNotify {
            changes,
            error,
            _watcher,
        })
    }

    pub fn watch(&self, py: Python, debounce_ms: u64, step_ms: u64, cancel_event: PyObject) -> PyResult<PyObject> {
        let event_not_none = !cancel_event.is_none(py);

        let mut max_time: Option<SystemTime> = None;
        let step_time = Duration::from_millis(step_ms);
        let mut last_size: usize = 0;
        let none: Option<bool> = None;
        loop {
            py.allow_threads(|| sleep(step_time));
            match py.check_signals() {
                Ok(_) => (),
                Err(_) => {
                    self.clear();
                    return Ok(none.to_object(py));
                }
            };

            if let Some(error) = self.error.lock().unwrap().as_ref() {
                self.clear();
                return Err(WatchgodRustInternalError::new_err(error.clone()));
            }

            if event_not_none && cancel_event.getattr(py, "is_set")?.call0(py)?.is_true(py)? {
                self.clear();
                return Ok(none.to_object(py));
            }

            let size = self.changes.lock().unwrap().len();
            if size > 0 {
                if size == last_size {
                    break;
                }
                last_size = size;

                let now = SystemTime::now();
                if let Some(max_time) = max_time {
                    if now > max_time {
                        break;
                    }
                } else {
                    max_time = Some(now + Duration::from_millis(debounce_ms));
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
    m.add("WatchgodRustInternalError", py.get_type::<WatchgodRustInternalError>())?;
    m.add_class::<RustNotify>()?;
    Ok(())
}
