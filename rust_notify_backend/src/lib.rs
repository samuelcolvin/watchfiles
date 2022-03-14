extern crate notify;
extern crate pyo3;

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::{create_exception};

use notify::{watcher, DebouncedEvent, RecommendedWatcher, RecursiveMode, Watcher};
use std::path::PathBuf;
use std::sync::mpsc::{channel, Receiver};
use std::time::Duration;

const VERSION: &str = env!("CARGO_PKG_VERSION");
create_exception!(_rtoml, WatchgodRustInternalError, PyRuntimeError);

#[pyclass]
struct RustNotifyWatcher {
    rx: Receiver<DebouncedEvent>,
    _watcher: RecommendedWatcher,
}

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
    fn py_new(watch_path: String, debounce_ms: u64) -> PyResult<Self> {
        // Create a channel to receive the events.
        let (tx, rx) = channel();

        // The notification back-end is selected based on the platform.
        let mut _watcher = watcher(tx, Duration::from_millis(debounce_ms)).unwrap();

        _watcher.watch(watch_path, RecursiveMode::Recursive).unwrap();
        Ok(RustNotifyWatcher { rx, _watcher })
    }

    // WARNING: keep this low as the wait is not cancellable by KeyboardInterrupt or similar
    // see https://stackoverflow.com/q/62364030/949890
    #[args(debounce_ms = 50)]
    pub fn check(&self, py: Python, debounce_ms: u64) -> PyResult<PyObject> {
        match self.rx.recv_timeout(Duration::from_millis(debounce_ms)) {
            Ok(event) => {
                let tuple: (u8, Option<String>) = match event {
                    DebouncedEvent::Create(path) => {
                        (CHANGE_ADDED, path_to_string(path))
                    }
                    DebouncedEvent::Write(path) => {
                        (CHANGE_ADDED, path_to_string(path))
                    }
                    DebouncedEvent::Chmod(path) => {
                        (CHANGE_MODIFIED, path_to_string(path))
                    }
                    DebouncedEvent::Remove(path) => {
                        (CHANGE_DELETED, path_to_string(path))
                    }
                    DebouncedEvent::Rename(old_path, new_path) => {
                        // two events, manually return from there
                        let e1 = (CHANGE_DELETED, path_to_string(old_path));
                        let e2 = (CHANGE_ADDED, path_to_string(new_path));
                        let v  = vec![e1, e2];
                        return Ok(v.to_object(py));
                    }
                    DebouncedEvent::Error(error, _) => {
                        return Err(WatchgodRustInternalError::new_err(format!("{:?}", error)))
                    }
                    // NoticeWrite, NoticeRemove, Rescan
                    _ => {
                        let none: Option<String> = None;
                        return Ok(none.to_object(py));
                    }
                };
                Ok(vec![tuple].to_object(py))
            }
            _ => {
                // timeout
                let none: Option<String> = None;
                return Ok(none.to_object(py));
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
