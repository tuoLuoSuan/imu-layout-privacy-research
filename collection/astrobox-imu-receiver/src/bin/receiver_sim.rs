// Local synthetic protocol harness; never opens Bluetooth, sockets or device APIs.
use imus5_receiver::receiver::{accept, export_text};
use std::{
    io::{self, BufRead},
    path::PathBuf,
};
fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("receiver_sim ROOT [--export TOKEN OUTPUT]");
        std::process::exit(2);
    }
    let root = PathBuf::from(&args[1]);
    if args.get(2).is_some_and(|s| s == "--export") {
        let result = (|| {
            if args.len() != 5 {
                return Err("invalid export arguments".to_string());
            }
            let mut f = std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&args[4])
                .map_err(|e| e.to_string())?;
            export_text(&root, &args[3], &mut f)
        })();
        if let Err(e) = result {
            eprintln!("{e}");
            std::process::exit(2);
        }
        return;
    }
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let ack = accept(&root, &line);
        match ack {
            Ok(a) => println!("{}", serde_json::to_string(&a).unwrap()),
            Err(e) => {
                let v: serde_json::Value = serde_json::from_str(&line).unwrap_or_default();
                println!(
                    "{}",
                    serde_json::json!({"p":"S5ERR1","t":v["t"],"s":v["s"],"error":e})
                );
            }
        }
    }
}
