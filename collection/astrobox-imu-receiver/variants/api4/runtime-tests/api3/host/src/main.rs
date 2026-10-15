use anyhow::{Result, anyhow};
use std::{pin::Pin, task::{Context, Poll}, sync::{Arc,Mutex}};
use wasmtime::{Config,Engine,Store,StoreContextMut};
use wasmtime::component::{Component,Linker,FutureReader,FutureConsumer,Source};
use futures_util::FutureExt;

struct Drain(Arc<Mutex<Vec<String>>>);
impl FutureConsumer<Vec<u32>> for Drain {
    type Item=String;
    fn poll_consume(self:Pin<&mut Self>,_:&mut Context<'_>,store:StoreContextMut<Vec<u32>>,mut source:Source<'_,String>,_:bool)->Poll<Result<()>> {
        let mut value=None;
        source.read(store,&mut value)?;
        if let Some(value)=value {self.0.lock().unwrap().push(value);}
        Poll::Ready(Ok(()))
    }
}

#[tokio::main(flavor="current_thread")]
async fn main()->Result<()> {
    let wasm=std::env::args().nth(1).ok_or_else(||anyhow!("wasm path required"))?;
    let mut config=Config::new();
    config.async_support(true).wasm_component_model(true).wasm_component_model_async(true);
    let engine=Engine::new(&config)?;
    let component=Component::from_file(&engine,&wasm)?;
    let mut linker=Linker::<Vec<u32>>::new(&engine);
    linker.define_unknown_imports_as_traps(&component)?;
    linker.allow_shadowing(true);
    {
        let mut host=linker.instance("research:api3-probe/host")?;
        host.func_wrap("draw",|mut s,(value,):(u32,)| {s.data_mut().push(value);Ok(())})?;
        host.func_wrap_concurrent("query",|accessor,():()| Box::pin(async move {
            let instance=accessor.instance();
            let f=accessor.with(|mut s|FutureReader::new(instance,&mut s,async move {
                tokio::task::yield_now().await;
                Ok::<u32,anyhow::Error>(42)
            }));
            Ok((f,))
        }))?;
    }
    let mut store=Store::new(&engine,Vec::<u32>::new());
    let instance=linker.instantiate_async(&mut store,&component).await?;
    let f=instance.get_typed_func::<(u32,),(FutureReader<String>,)>(&mut store,"event")?;
    let consumed=Arc::new(Mutex::new(Vec::new()));
    for (n,action) in [0u32,1,2,0,2].into_iter().enumerate() {
        let result=std::panic::AssertUnwindSafe(async {
            let (r,)=f.call_async(&mut store,(action,)).await?;
            f.post_return_async(&mut store).await?;
            r.pipe(&mut store,Drain(consumed.clone()));
            tokio::task::yield_now().await;
            Ok::<(),anyhow::Error>(())
        }).catch_unwind().await;
        match result {
            Ok(Ok(()))=>println!("event {n} action {action}: returned; draws={:?}, consumed={:?}",store.data(),consumed.lock().unwrap()),
            Ok(Err(e))=>{println!("event {n} ERROR {e:#}");},
            Err(p)=> {
                let s=p.downcast_ref::<&str>().map(|x|(*x).to_owned()).or_else(||p.downcast_ref::<String>().cloned()).unwrap_or_default();
                println!("event {n} PANIC {s}");
                return Err(anyhow!(s));
            }
        }
    }
    Ok(())
}
