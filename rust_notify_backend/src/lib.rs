extern crate notify;
extern crate pyo3;

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::create_exception;

use std::collections::HashSet;
use std::path::PathBuf;
use std::sync::mpsc::{channel, Receiver};
use std::time::{Duration, SystemTime};

use notify::{raw_watcher, RawEvent, op, RecommendedWatcher, RecursiveMode, Watcher};

const VERSION: &str = env!("CARGO_PKG_VERSION");
create_exception!(_rust_notify_backend, WatchgodRustInternalError, PyRuntimeError);

#[pyclass]
struct RustNotifyWatcher {
    rx: Receiver<RawEvent>,
    _watcher: RecommendedWatcher,
}

// these need to match `watchgod/watcher.py::Change`
const CHANGE_ADDED: u8 = 1;
const CHANGE_MODIFIED: u8 = 2;
const CHANGE_DELETED: u8 = 3;

fn path_to_string(p: PathBuf) -> Option<String> {
    match p.to_str() {
        Some(s) => Some(s.to_string()),
        None => None,
    }
}

#[pymethods]
impl RustNotifyWatcher {
    #[new]
    fn py_new(watch_path: String) -> PyResult<Self> {
        let (tx, rx) = channel();

        let mut _watcher = raw_watcher(tx).unwrap();

        _watcher.watch(watch_path, RecursiveMode::Recursive).unwrap();
        Ok(RustNotifyWatcher { rx, _watcher })
    }

    // WARNING: keep step_size low as the wait is not cancelled by KeyboardInterrupt
    #[args(debounce_ms = 1600, step_size = 50)]
    pub fn check(&self, py: Python, debounce_ms: u64, step_size: u64) -> PyResult<PyObject> {
        let mut changes = Vec::<(u8, Option<String>)>::new();
        let max_time = SystemTime::now() + Duration::from_millis(debounce_ms);
        let recv_timeout = Duration::from_millis(step_size);
        let mut rename_cookies = HashSet::<u32>::new();
        loop {
            py.check_signals()?;
            let new_changes = match self.rx.recv_timeout(recv_timeout) {
                Ok(event) => {
                    // println!("event: {:?}", event);
                    match event.op {
                        Ok(op) => {
                            if let Some(path) = event.path {
                                let change: Option<u8> = match op {
                                    op::CREATE => Some(CHANGE_ADDED),
                                    op::CHMOD | op::WRITE => Some(CHANGE_MODIFIED),
                                    op::REMOVE => Some(CHANGE_DELETED),
                                    op::RENAME => {
                                        if let Some(cookie) = event.cookie {
                                            if rename_cookies.contains(&cookie) {
                                                Some(CHANGE_ADDED)
                                            } else {
                                                rename_cookies.insert(cookie);
                                                Some(CHANGE_DELETED)
                                            }
                                        } else {
                                            None
                                        }
                                    },
                                    op::RESCAN => None,
                                    _ => {
                                        if op.contains(op::REMOVE) {
                                            Some(CHANGE_DELETED)
                                        } else if op.contains(op::CREATE) {
                                            Some(CHANGE_ADDED)
                                        } else if op == op::Op::empty() {
                                            None
                                        } else {
                                            print!("event with unknown op {:?}, path={:?}", op, path);
                                            None
                                            // let msg = format!("event with unknown op {:?}, path={:?}", op, path);
                                            // return Err(WatchgodRustInternalError::new_err(msg));
                                        }
                                    },
                                };
                                if let Some(change) = change {
                                    let path = path_to_string(path);
                                    changes.push((change, path));
                                    true
                                } else {
                                    false
                                }
                            } else {
                                let msg = format!("event with no path, op={:?}", op);
                                return Err(WatchgodRustInternalError::new_err(msg));
                            }
                        },
                        Err(e) => {
                            let msg = format!("{}", e);
                            return Err(WatchgodRustInternalError::new_err(msg));
                        },
                    }
                },
                _ => {
                    // timeout
                    false
                }
            };

            if !new_changes || SystemTime::now() > max_time {
                return Ok(changes.to_object(py));
            }
        }
    }
}

#[pymodule]
fn _rust_notify_backend(py: Python, m: &PyModule) -> PyResult<()> {
    m.add("VERSION", VERSION)?;
    m.add("WatchgodRustInternalError", py.get_type::<WatchgodRustInternalError>())?;
    m.add_class::<RustNotifyWatcher>()?;
    Ok(())
}
