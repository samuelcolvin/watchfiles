extern crate notify;
extern crate pyo3;

use std::collections::HashSet;
use std::path::PathBuf;
use std::sync::mpsc::channel;
use std::time::{Duration, SystemTime};

use pyo3::create_exception;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use notify::{op, raw_watcher, Error as NotifyError, RecursiveMode, Watcher};

const VERSION: &str = env!("CARGO_PKG_VERSION");
create_exception!(_rust_notify_backend, WatchgodRustInternalError, PyRuntimeError);

// these need to match `watchgod/watcher.py::Change`
const CHANGE_ADDED: u8 = 1;
const CHANGE_MODIFIED: u8 = 2;
const CHANGE_DELETED: u8 = 3;

fn path_to_string(p: PathBuf) -> Result<String, String> {
    match p.to_str() {
        Some(s) => Ok(s.to_string()),
        None => Err(format!("Unable to decode path {:?} to string", p)),
    }
}

fn string_err(e: NotifyError) -> String {
    format!("{:?}", e)
}

#[pyfunction(watch_path, debounce_ms = 1600, step_size = 50)]
fn check(py: Python, watch_path: String, debounce_ms: u64, step_size: u64) -> PyResult<PyObject> {
    let changes = py
        .allow_threads(move || check_internal(watch_path, debounce_ms, step_size))
        .map_err(|msg| WatchgodRustInternalError::new_err(msg))?;
    Ok(changes.to_object(py))
}

fn check_internal(watch_path: String, debounce_ms: u64, step_size: u64) -> Result<Vec<(u8, String)>, String> {
    let (tx, rx) = channel();

    let mut watcher = raw_watcher(tx).map_err(string_err)?;

    watcher
        .watch(watch_path, RecursiveMode::Recursive)
        .map_err(string_err)?;

    let mut changes = Vec::<(u8, String)>::new();
    let max_time = SystemTime::now() + Duration::from_millis(debounce_ms);
    let recv_timeout = Duration::from_millis(step_size);
    let mut rename_cookies = HashSet::<u32>::new();
    loop {
        let new_changes = match rx.recv_timeout(recv_timeout) {
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
                                }
                                op::RESCAN => None,
                                _ => {
                                    if op.contains(op::REMOVE) {
                                        Some(CHANGE_DELETED)
                                    } else if op.contains(op::CREATE) {
                                        Some(CHANGE_ADDED)
                                    } else if op == op::Op::empty() {
                                        None
                                    } else {
                                        let msg = format!("event with unknown op {:?}, path={:?}", op, path);
                                        return Err(msg);
                                    }
                                }
                            };
                            if let Some(change) = change {
                                let path = path_to_string(path)?;
                                changes.push((change, path));
                                true
                            } else {
                                false
                            }
                        } else {
                            // not sure how this happens, please report if you see this error
                            let msg = format!("event unexpected has no path, op={:?}", op);
                            return Err(msg);
                        }
                    }
                    Err(e) => {
                        let msg = format!("{}", e);
                        return Err(msg);
                    }
                }
            }
            _ => {
                // timeout
                false
            }
        };

        if !new_changes || SystemTime::now() > max_time {
            return Ok(changes);
        }
    }
}

#[pymodule]
fn _rust_notify_backend(py: Python, m: &PyModule) -> PyResult<()> {
    m.add("VERSION", VERSION)?;
    m.add("WatchgodRustInternalError", py.get_type::<WatchgodRustInternalError>())?;
    m.add_wrapped(wrap_pyfunction!(check))?;
    Ok(())
}
