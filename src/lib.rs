extern crate crossbeam_channel;
extern crate notify;
extern crate pyo3;

use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::sleep;
use std::time::{Duration, SystemTime};

use pyo3::create_exception;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use notify::event::{Event, EventKind, ModifyKind};
use notify::{
    recommended_watcher, Error as NotifyError, RecommendedWatcher, RecursiveMode, Result as NotifyResult, Watcher,
};

create_exception!(_rust_notify, WatchgodRustInternalError, PyRuntimeError);

// these need to match `watchgod/watcher.py::Change`
const CHANGE_ADDED: u8 = 1;
const CHANGE_MODIFIED: u8 = 2;
const CHANGE_DELETED: u8 = 3;

#[pyfunction]
fn rust_watch(
    py: Python,
    watch_path: String,
    debounce_ms: u64,
    step_ms: u64,
    cancel_event: PyObject,
) -> PyResult<PyObject> {
    let cancel_event_given = !cancel_event.is_none(py);
    let changes = Arc::new(Mutex::new(Vec::<(u8, String)>::new()));
    let changes_clone = changes.clone();
    let error: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));
    let error_clone = error.clone();
    let last_rename = AtomicBool::new(false);

    let mut watcher: RecommendedWatcher = recommended_watcher(move |res: NotifyResult<Event>| match res {
        Ok(event) => {
            println!("event: {:?}", event);
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
                    EventKind::Modify(ModifyKind::Data(_)) => CHANGE_MODIFIED,
                    EventKind::Modify(ModifyKind::Metadata(_)) => return,
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
                changes_clone.lock().unwrap().push((change, path));
            }
        }
        Err(e) => {
            *error_clone.lock().unwrap() = Some(format!("error in underlying watcher: {}", e));
        }
    })
    .map_err(map_notify_error)?;

    watcher
        .watch(Path::new(&watch_path), RecursiveMode::Recursive)
        .map_err(map_notify_error)?;

    let mut max_time: Option<SystemTime> = None;
    let step_time = Duration::from_millis(step_ms);
    let mut last_size: usize = 0;
    loop {
        py.allow_threads(|| sleep(step_time));
        py.check_signals()?;

        if let Some(error) = error.lock().unwrap().as_ref() {
            return Err(WatchgodRustInternalError::new_err(error.clone()));
        }

        if cancel_event_given && cancel_event.getattr(py, "is_set")?.call0(py)?.is_true(py)? {
            break;
        }

        let size = changes.lock().unwrap().len();
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
    return Ok(changes.lock().unwrap().to_object(py));
}

fn map_notify_error(e: NotifyError) -> PyErr {
    WatchgodRustInternalError::new_err(format!("{}", e))
}

#[pymodule]
fn _rust_notify(py: Python, m: &PyModule) -> PyResult<()> {
    m.add("WatchgodRustInternalError", py.get_type::<WatchgodRustInternalError>())?;
    m.add_wrapped(wrap_pyfunction!(rust_watch))?;
    Ok(())
}