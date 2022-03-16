extern crate crossbeam_channel;
extern crate notify;
extern crate pyo3;

use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::sleep;
use std::time::{Duration, SystemTime};

use pyo3::create_exception;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use notify::event::{Event, EventKind, ModifyKind};
use notify::{recommended_watcher, RecommendedWatcher, RecursiveMode, Result as NotifyResult, Watcher};

const VERSION: &str = env!("CARGO_PKG_VERSION");
create_exception!(_rust_notify_backend, WatchgodRustInternalError, PyRuntimeError);

// these need to match `watchgod/watcher.py::Change`
const CHANGE_ADDED: u8 = 1;
const CHANGE_MODIFIED: u8 = 2;
const CHANGE_DELETED: u8 = 3;

fn path_to_string(p: &PathBuf) -> Result<String, PyErr> {
    match p.to_str() {
        Some(s) => Ok(s.to_string()),
        None => Err(WatchgodRustInternalError::new_err(format!(
            "Unable to decode path {:?} to string",
            p
        ))),
    }
}

// fn map_err(e: NotifyError) -> PyErr {
//     WatchgodRustInternalError::new_err(format!("{:?}", e))
// }

#[pyfunction(watch_path, debounce_ms = 1600, step_ms = 50)]
fn check(py: Python, watch_path: String, debounce_ms: u64, step_ms: u64) -> PyResult<PyObject> {
    let changes = Arc::new(Mutex::new(Vec::<(u8, String)>::new()));
    let changes_ref = changes.clone();
    let last_rename = AtomicBool::new(false);

    let mut watcher: RecommendedWatcher = recommended_watcher(move |res: NotifyResult<Event>| match res {
        Ok(event) => {
            println!("event: {:?}", event);
            if let Some(p) = event.paths.first() {
                let path = path_to_string(p).unwrap();
                let change = match event.kind {
                    EventKind::Create(_) => CHANGE_ADDED,
                    EventKind::Modify(ModifyKind::Data(_)) => CHANGE_MODIFIED,
                    EventKind::Modify(ModifyKind::Metadata(_)) => return,
                    EventKind::Modify(ModifyKind::Name(_)) => {
                        // this just alternates `last_rename` between true and false
                        let new_path = last_rename.fetch_xor(true, Ordering::SeqCst);
                        if new_path {
                            CHANGE_ADDED
                        } else {
                            CHANGE_DELETED
                        }
                    },
                    EventKind::Remove(_) => CHANGE_DELETED,
                    _ => return,
                };
                changes_ref.lock().unwrap().push((change, path));
            }
        }
        Err(e) => {
            println!("error: {:?}", e);
            // let msg = format!("{}", e);
            // return Err(WatchgodRustInternalError::new_err(msg));
        }
    })
    .unwrap();

    watcher.watch(Path::new(&watch_path), RecursiveMode::Recursive).unwrap();

    let debounce_time = SystemTime::now() + Duration::from_millis(debounce_ms);
    let step_time = Duration::from_millis(step_ms);
    let mut last_size: usize = 0;
    loop {
        py.allow_threads(|| sleep(step_time));
        py.check_signals()?;
        let size = changes.lock().unwrap().len();

        if size > 0 && (size == last_size || SystemTime::now() > debounce_time) {
            return Ok(changes.lock().unwrap().to_object(py));
        }
        last_size = size;
    }
}

#[pymodule]
fn _rust_notify_backend(py: Python, m: &PyModule) -> PyResult<()> {
    m.add("VERSION", VERSION)?;
    m.add("WatchgodRustInternalError", py.get_type::<WatchgodRustInternalError>())?;
    m.add_wrapped(wrap_pyfunction!(check))?;
    Ok(())
}
