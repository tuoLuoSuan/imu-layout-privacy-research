use wasmtime::{AsContextMut,Config,Engine,Store,Result,Error};
use wasmtime::component::{Component,ComponentType,Func,Instance,Lift,Linker,Lower,Resource,ResourceAny,ResourceTable,ResourceType,Val};

#[derive(Clone,Default)]
struct Element {texts:Vec<String>}
#[derive(Default)]
struct Context {
    table:ResourceTable,
    renders:Vec<Vec<String>>,
    queries:u32,
    registrations:u32,
    sends:u32,
    deny:bool,
    block_query:bool,
    query_entered:Arc<Notify>,
    query_release:Arc<Notify>,
}
#[derive(ComponentType,Lift,Lower)]
#[component(record)]
struct Device {name:String,addr:String}

fn own_element(s:&mut wasmtime::StoreContextMut<Context>,el:Element)->Result<Val>{
    let r=s.data_mut().table.push(el)?;
    Ok(Val::Resource(ResourceAny::try_from_resource(r,&mut *s)?))
}
fn get_element(s:&mut wasmtime::StoreContextMut<Context>,v:&Val)->Result<(Resource<Element>,Element)>{
    let Val::Resource(r)=v else {return Err(Error::msg("expected UI resource"))};
    let r=r.try_into_resource::<Element>(&mut *s)?;
    let el=s.data().table.get(&r)?.clone();
    Ok((r,el))
}
fn find(instance:Instance,store:&mut Store<Context>,interface:&str,name:&str)->Func{
    let (_,i)=instance.get_export(store.as_context_mut(),None,interface).expect("event interface");
    let (_,f)=instance.get_export(store.as_context_mut(),Some(&i),name).expect("event function");
    instance.get_func(store.as_context_mut(),&f).expect("function")
}

#[tokio::main(flavor="current_thread")]
async fn main()->Result<()> {
    let path=std::env::args().nth(1).ok_or_else(||Error::msg("actual component path required"))?;
    let deny=std::env::args().any(|s|s=="deny");
    let busy=std::env::args().any(|s|s=="busy");
    let mut cfg=Config::new();cfg.wasm_component_model(true).wasm_component_model_async(true);
    let engine=Engine::new(&cfg)?;
    let component=Component::from_file(&engine,path)?;
    let mut linker=Linker::<Context>::new(&engine);
    linker.define_unknown_imports_as_traps(&component)?;
    linker.allow_shadowing(true);
    {
        let mut ui=linker.instance("astrobox:psys-host-v4/ui")?;
        ui.resource("element",ResourceType::host::<Element>(),|mut s,id|{
            s.data_mut().table.delete(Resource::<Element>::new_own(id))?;
            Ok(())
        })?;
        ui.func_new("[constructor]element",|mut s,_,params,results|{
            let mut el=Element::default();
            if let Val::Option(Some(v))=&params[1] {if let Val::String(v)=&**v {el.texts.push(v.clone());}}
            results[0]=own_element(&mut s,el)?;Ok(())
        })?;
        for method in ["without-default-styles","size","text-color","on","bg","padding","radius","flex","flex-direction","width-full","min-height","gap","border","child"] {
            let name=format!("[method]element.{method}");
            ui.func_new(&name,move|mut s,_,params,results|{
                let (_,mut el)=get_element(&mut s,&params[0])?;
                if method=="child" {
                    let (r,child)=get_element(&mut s,&params[1])?;
                    el.texts.extend(child.texts);
                    s.data_mut().table.delete(r)?;
                }
                results[0]=own_element(&mut s,el)?;Ok(())
            })?;
        }
        ui.func_new("render",|mut s,_,params,_|{
            let (r,el)=get_element(&mut s,&params[1])?;
            s.data_mut().renders.push(el.texts);
            s.data_mut().table.delete(r)?;
            Ok(())
        })?;
    }
    linker.instance("astrobox:psys-host-v4/device")?.func_wrap_concurrent("get-connected-device-list",|a,():()|Box::pin(async move{
        let (block,entered,release)=a.with(|mut s|{let c=s.data_mut();(c.block_query,c.query_entered.clone(),c.query_release.clone())});
        if block {entered.notify_one();release.notified().await;}
        tokio::task::yield_now().await;
        a.with(|mut s|s.data_mut().queries+=1);
        Ok((vec![Device{name:"Synthetic S5".into(),addr:"SYNTHETIC".into()}],))
    }))?;
    linker.instance("astrobox:psys-host-v4/register")?.func_wrap_concurrent("register-interconnect-recv",|a,(addr,package):(String,String)|Box::pin(async move{
        assert_eq!(addr,"SYNTHETIC");assert_eq!(package,"org.imuresearch.s5probe");
        tokio::task::yield_now().await;
        let deny=a.with(|mut s|{s.data_mut().registrations+=1;s.data_mut().deny});
        let result=if deny {Err("synthetic permission denied".to_string())} else {Ok(())};
        Ok((result,))
    }))?;
    linker.instance("astrobox:psys-host-v4/interconnect")?.func_wrap_concurrent("send-qaic-message",|a,(addr,package,data):(String,String,String)|Box::pin(async move{
        assert_eq!(addr,"SYNTHETIC");assert_eq!(package,"org.imuresearch.s5probe");assert_eq!(data,"{\"p\":\"S5HELLO1\"}");
        tokio::task::yield_now().await;
        a.with(|mut s|s.data_mut().sends+=1);
        Ok((Ok::<(),String>(()),))
    }))?;
    // Empty synthetic preopens/environment: refresh sees no recorded files. No real data directory is exposed.
    for (name,_) in component.component_type().imports(&engine) {
        if name.starts_with("wasi:filesystem/preopens@") {
            let mut p=linker.instance(name)?;
            p.resource("descriptor",ResourceType::host::<()>(),|_,_|Ok(()))?;
            p.func_new("get-directories",|_,_,_,r|{r[0]=Val::List(vec![]);Ok(())})?;
        }
        if name.starts_with("wasi:cli/environment@") {
            let mut p=linker.instance(name)?;
            p.func_new("get-environment",|_,_,_,r|{r[0]=Val::List(vec![]);Ok(())})?;
            p.func_new("get-arguments",|_,_,_,r|{r[0]=Val::List(vec![]);Ok(())})?;
            p.func_new("initial-cwd",|_,_,_,r|{r[0]=Val::Option(None);Ok(())})?;
        }
    }
    let mut store=Store::new(&engine,Context{deny,block_query:busy,..Context::default()});
    let instance=linker.instantiate_async(&mut store,&component).await?;
    let render=find(instance,&mut store,"astrobox:psys-plugin-v4/event","on-ui-render");
    let click=find(instance,&mut store,"astrobox:psys-plugin-v4/event","on-ui-event");
    let load=find(instance,&mut store,"astrobox:psys-plugin-v4/lifecycle","on-load");
    store.run_concurrent(async|a|->Result<()>{
        load.call_concurrent(a,&[],&mut[]).await?;
        for n in 0..64 {
            render.call_concurrent(a,&[Val::String("test-root".into())],&mut[]).await?;
            let mut result=[Val::String(String::new())];
            click.call_concurrent(a,&[Val::String("probe".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut result).await?;
            assert!(a.with(|mut s|s.data_mut().renders.last().unwrap().iter().any(|v|v.contains("运行检查通过"))));
            if n%16==0 {println!("actual WASM UI checks completed: {}",n+1);}
        }
        let mut result=[Val::String(String::new())];
        if busy {
            let (entered,release)=a.with(|mut s|{let c=s.data_mut();(c.query_entered.clone(),c.query_release.clone())});
            let first=async {
                let mut r=[Val::String(String::new())];
                click.call_concurrent(a,&[Val::String("prepare".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut r).await
            };
            let second=async {
                entered.notified().await;
                let mut r=[Val::String(String::new())];
                let res=click.call_concurrent(a,&[Val::String("prepare".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut r).await;
                release.notify_one();
                res
            };
            let (r1,r2)=tokio::join!(first,second);r1?;r2?;
        } else {
            for _ in 0..2 {
                click.call_concurrent(a,&[Val::String("prepare".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut result).await?;
            }
        }
        click.call_concurrent(a,&[Val::String("probe".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut result).await?;
        Ok(())
    }).await??;
    let ctx=store.data();
    assert!(ctx.renders.iter().flatten().any(|v|v.contains("v0.2.0")));
    if deny {
        assert_eq!((ctx.queries,ctx.registrations,ctx.sends),(2,2,0));
        assert!(ctx.renders.iter().flatten().any(|v|v.contains("synthetic permission denied")));
    } else {
        assert_eq!((ctx.queries,ctx.registrations,ctx.sends),(1,1,if busy {1}else {2}));
        assert!(ctx.renders.iter().flatten().any(|v|v.contains("已准备接收")));
    }
    println!("PASS actual component: 64 render/check cycles, 2 preparation callbacks, 1 recovery check; queries={} registrations={} sends={} deny={deny} busy={busy}; synthetic host only",ctx.queries,ctx.registrations,ctx.sends);
    Ok(())
}
use std::sync::Arc;
use tokio::sync::Notify;
