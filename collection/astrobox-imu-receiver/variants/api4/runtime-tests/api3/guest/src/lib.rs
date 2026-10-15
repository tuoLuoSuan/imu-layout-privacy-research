#[cfg(feature = "async-export")]
wit_bindgen::generate!({ path: "wit", world: "probe", async: ["export:event"] });
#[cfg(not(feature = "async-export"))]
wit_bindgen::generate!({ path: "wit", world: "probe" });

struct Probe;

async fn work(action: u32) {
    if action == 1 { wit_bindgen::yield_async().await; }
    if action == 2 {
        let value = research::api3_probe::host::query().await;
        research::api3_probe::host::draw(value);
    }
}

#[cfg(feature = "async-export")]
impl Guest for Probe {
    async fn event(action: u32) -> wit_bindgen::FutureReader<String> {
        let (writer, reader) = wit_future::new::<String>(String::new);
        research::api3_probe::host::draw(action);
        wit_bindgen::spawn(async move {
            work(action).await;
            let _ = writer.write("complete".into()).await;
        });
        reader
    }
}

#[cfg(not(feature = "async-export"))]
impl Guest for Probe {
    fn event(action: u32) -> wit_bindgen::FutureReader<String> {
        let (writer, reader) = wit_future::new::<String>(String::new);
        research::api3_probe::host::draw(action);
        #[cfg(feature = "drop-after")]
        {
            wit_bindgen::block_on(work(action));
            drop(writer);
        }
        #[cfg(all(feature = "blocking", not(feature = "drop-after")))]
        {
            wit_bindgen::block_on(async move {
                work(action).await;
                drop(writer);
            });
        }
        #[cfg(not(any(feature = "blocking", feature = "drop-after")))]
        wit_bindgen::spawn(async move {
            work(action).await;
            let _ = writer.write("complete".into()).await;
        });
        reader
    }
}
export!(Probe);
