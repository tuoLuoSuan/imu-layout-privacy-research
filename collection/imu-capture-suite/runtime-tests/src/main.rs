use wasmtime_wasi::{WasiCtx,WasiCtxBuilder,WasiCtxView,WasiView,FsPerms};
use wasmtime::{AsContextMut,Config,Engine,Store,Result,Error};
use wasmtime::component::{Component,ComponentType,Func,Instance,Lift,Linker,Lower,Resource,ResourceAny,ResourceTable,ResourceType,Val};

#[derive(Clone,Default)]
struct Element {texts:Vec<String>}
struct Context {
    wasi:WasiCtx,
    replies:Vec<String>,
    run_root:String,
    saved_bytes:Vec<u8>,
    save_finished:bool,
    save_cancelled:bool,
    table:ResourceTable,
    renders:Vec<Vec<String>>,
    queries:u32,
    registrations:u32,
    sends:u32,
    http_starts:u32,
    http_stops:u32,
    deny:bool,
    block_query:bool,
    reply_deny:bool,
    query_entered:Arc<Notify>,
    query_release:Arc<Notify>,
}
#[derive(ComponentType,Lift,Lower)]
#[component(record)]
struct Device {name:String,addr:String}
#[derive(ComponentType,Lift,Lower)]
#[component(record)]
struct Filter {multiple:bool,extensions:Vec<String>,#[component(name="default-directory")]default_directory:String,#[component(name="default-file-name")]default_file_name:String}
#[derive(ComponentType,Lift,Lower)]
#[component(record)]
struct SaveSession {#[component(name="session-id")]session_id:u64,name:String}

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
    let v2=std::env::args().any(|s|s=="v2");
    let reply_deny=std::env::args().any(|s|s=="reply-denied");
    let structure_only=std::env::args().any(|s|s=="structure-only");
    let enveloped=std::env::args().any(|s|s=="enveloped");
    let mut cfg=Config::new();cfg.wasm_component_model(true).wasm_component_model_async(true);
    let engine=Engine::new(&cfg)?;
    let component=Component::from_file(&engine,path)?;
    let mut linker=Linker::<Context>::new(&engine);
    linker.allow_shadowing(true);
    wasmtime_wasi::p2::add_to_linker_async(&mut linker)?;
    wasmtime_wasi::p3::add_to_linker(&mut linker)?;
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
        assert_eq!(addr,"SYNTHETIC");assert_eq!(package,"org.imuresearch.s5joint");
        tokio::task::yield_now().await;
        let deny=a.with(|mut s|{s.data_mut().registrations+=1;s.data_mut().deny});
        let result=if deny {Err("synthetic permission denied".to_string())} else {Ok(())};
        Ok((result,))
    }))?;
    linker.instance("astrobox:psys-host-v4/interconnect")?.func_wrap_concurrent("send-qaic-message",|a,(addr,package,data):(String,String,String)|Box::pin(async move{
        assert_eq!(addr,"SYNTHETIC");assert_eq!(package,"org.imuresearch.s5joint");
        tokio::task::yield_now().await;
        let rejected=a.with(|mut s|{let c=s.data_mut();c.sends+=1;let denied=c.reply_deny&&data.contains("J_CLK_REP1");
        let v:serde_json::Value=serde_json::from_str(&data).unwrap();
        if v["p"]=="J_DATA_ACK1" {
            let text=std::fs::read_to_string(std::path::Path::new(&c.run_root).join(format!("joint_records/{}.jsonl",v["native_sid"].as_str().unwrap()))).unwrap();
            assert!(text.contains("watch_data"),"ACK before persistence");
        }
        c.replies.push(data);denied});
        Ok((if rejected {Err("synthetic reply denied".to_string())}else{Ok(())},))
    }))?;
    {
        let mut dialog=linker.instance("astrobox:psys-host-v4/dialog")?;
        dialog.func_wrap_concurrent("save-file-start",|a,(filter,):(Filter,)|Box::pin(async move{
            assert_eq!(filter.extensions,vec!["jsonl"]);assert!(filter.default_file_name.ends_with(".jsonl"));
            let cancel=a.with(|mut s|s.data_mut().save_cancelled);
            let r:std::result::Result<SaveSession,String>=if cancel{Err("synthetic cancel".into())}else{Ok(SaveSession{session_id:1,name:filter.default_file_name})};Ok((r,))
        }))?;
        dialog.func_wrap_concurrent("save-file-write-chunk",|a,(id,bytes):(u64,Vec<u8>)|Box::pin(async move{
            assert_eq!(id,1);assert!(bytes.len()<=8192);a.with(|mut s|s.data_mut().saved_bytes.extend(bytes));Ok((Ok::<(),String>(()),))
        }))?;
        dialog.func_wrap_concurrent("save-file-finish",|a,(id,):(u64,)|Box::pin(async move{
            assert_eq!(id,1);a.with(|mut s|s.data_mut().save_finished=true);Ok((Ok::<(),String>(()),))
        }))?;
        dialog.func_wrap_concurrent("save-file-abort",|_,(_id,):(u64,)|Box::pin(async move{Ok(())}))?;
    }


    {
        let mut http=linker.instance("astrobox:psys-host-v4/http-server")?;
        http.func_wrap_concurrent("start",|a,(opts,):(HttpOptions,)|Box::pin(async move{
            assert!(!opts.bind_all_interfaces);assert_eq!(opts.port,38741);
            a.with(|mut s|s.data_mut().http_starts+=1);
            let denied=std::env::args().any(|s|s=="http-denied");
            let r=if denied{Err("synthetic HTTP permission denied".to_string())}else{Ok(HttpInfo{id:23,host:"127.0.0.1".into(),port:38741,url:"http://127.0.0.1:38741".into()})};
            Ok((r,))
        }))?;
        http.func_wrap_concurrent("stop",|a,(id,):(u32,)|Box::pin(async move{assert_eq!(id,23);a.with(|mut s|s.data_mut().http_stops+=1);Ok((Ok::<(),String>(()),))}))?;
        http.func_wrap("list-servers",|_,():()|Ok((Vec::<HttpInfo>::new(),)))?;
    }
    let run_root=std::env::args().nth(2).ok_or_else(||Error::msg("fresh directory required"))?;
    std::fs::create_dir(&run_root)?;
    let collision=std::env::args().any(|s|s=="collision");
    let journal=std::path::Path::new(&run_root).join("joint_records/native-session.jsonl");
    if collision{std::fs::create_dir(journal.parent().unwrap())?;std::fs::write(&journal,b"PREEXISTING")?;}
    let mut wasi=WasiCtxBuilder::new();wasi.preopened_dir(&run_root,".",FsPerms::ReadWrite)?;
    let ctx=Context{wasi:wasi.build(),table:ResourceTable::new(),renders:Vec::new(),replies:Vec::new(),run_root:run_root.clone(),saved_bytes:Vec::new(),save_finished:false,save_cancelled:std::env::args().any(|s|s=="save-cancelled"),queries:0,registrations:0,sends:0,http_starts:0,http_stops:0,deny,block_query:busy,reply_deny,query_entered:Arc::new(Notify::new()),query_release:Arc::new(Notify::new())};
    let mut store=Store::new(&engine,ctx);let instance=linker.instantiate_async(&mut store,&component).await?;
    let render=find(instance,&mut store,"astrobox:psys-plugin-v4/event","on-ui-render");
    let click=find(instance,&mut store,"astrobox:psys-plugin-v4/event","on-ui-event");
    let load=find(instance,&mut store,"astrobox:psys-plugin-v4/lifecycle","on-load");
    let event=find(instance,&mut store,"astrobox:psys-plugin-v4/event","on-event");
    let handle=find(instance,&mut store,"astrobox:psys-plugin-v4/http","handle");
    store.run_concurrent(async|a|->Result<()>{
        load.call_concurrent(a,&[],&mut[]).await?;render.call_concurrent(a,&[Val::String("joint-root".into())],&mut[]).await?;
        let mut result=[Val::String(String::new())];
        if busy{
            let (entered,release)=a.with(|mut s|{let c=s.data_mut();(c.query_entered.clone(),c.query_release.clone())});
            let first=async{let mut r=[Val::String(String::new())];click.call_concurrent(a,&[Val::String("prepare".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut r).await};
            let second=async{entered.notified().await;let mut r=[Val::String(String::new())];click.call_concurrent(a,&[Val::String("cancel".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut r).await?;release.notify_one();Ok::<(),Error>(())};
            let (x,y)=tokio::join!(first,second);x?;y?;return Ok(());
        }
        click.call_concurrent(a,&[Val::String("prepare".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut result).await?;
        if deny||std::env::args().any(|s|s=="http-denied"){return Ok(());}
        let mut hr=[http_empty_response()];
        handle.call_concurrent(a,&[Val::U32(23),http_request(r#"{"kind":"native_clock_req","sid":"native-session","seq":0,"nonce":"nonce-0","n1_ns":1000000000}"#)],&mut hr).await?;
        let (status,rep)=http_response(&hr[0]);
        if collision{assert_eq!(status,500);assert_eq!(std::fs::read(&journal)?,b"PREEXISTING");return Ok(());}
        assert_eq!(status,200);assert_eq!(rep["nonce"],"nonce-0");assert_eq!(rep["watch_finished"],false);
        handle.call_concurrent(a,&[Val::U32(23),http_request(r#"{"sid":"x","sid":"y"}"#)],&mut hr).await?;assert_eq!(http_response(&hr[0]).0,400);
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(r#"{"p":"J_HELLO1","sid":"watch-session","w1_ms":1792300000000}"#.into())],&mut result).await?;
        let hello=a.with(|mut s|s.data_mut().replies.last().unwrap().clone());assert_eq!(serde_json::from_str::<serde_json::Value>(&hello)?["native_sid"],"native-session");
        let w1=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_millis()as u64;
        let req=serde_json::json!({"p":"J_CLK_REQ1","sid":"watch-session","native_sid":"native-session","seq":0,"w1_ms":w1}).to_string();
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(req)],&mut result).await?;
        let rep=a.with(|mut s|s.data_mut().replies.last().unwrap().clone());let rep:serde_json::Value=serde_json::from_str(&rep)?;assert_eq!(rep["p"],"J_CLK_REP1");
        if reply_deny{return Ok(());}
        let w4=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_millis()as u64+1;
        let obs=serde_json::json!({"p":"J_CLK_OBS1","sid":"watch-session","native_sid":"native-session","seq":0,"w1_ms":w1,"w4_ms":w4,"p2_us":rep["p2_us"],"p3_us":rep["p3_us"]}).to_string();
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(obs)],&mut result).await?;
        let payload=format!("[[0,{},1.25,2.5,9.81],[1,{},1.125,2.25,9.75]]",w1+1,w1+61);
        let data=serde_json::json!({"p":"J_DATA1","sid":"watch-session","native_sid":"native-session","index":0,"payload":payload,"crc32":crc(payload.as_bytes())}).to_string();
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(data.clone())],&mut result).await?;
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(data)],&mut result).await?;
        let end=serde_json::json!({"p":"J_END1","sid":"watch-session","native_sid":"native-session","count":2,"blocks":1,"start_ms":w1,"stop_ms":w1+20000,"stop_reason":"duration","clock_observations":1,"acquisition":{"accepted_rows":2}}).to_string();
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(end)],&mut result).await?;
        handle.call_concurrent(a,&[Val::U32(23),http_request(r#"{"kind":"native_clock_req","sid":"native-session","seq":1,"nonce":"nonce-1","n1_ns":2000000000}"#)],&mut hr).await?;
        let (status,rep)=http_response(&hr[0]);assert_eq!(status,200);assert_eq!(rep["watch_finished"],true);assert_eq!(rep["watch_clock_observations"],1);assert_eq!(rep["watch_rows"],2);
        let original=std::fs::read(&journal)?;
        handle.call_concurrent(a,&[Val::U32(23),http_path_request("/export",r#"{"kind":"export_session","sid":"native-session","nonce":"export-nonce"}"#)],&mut hr).await?;
        let(status,headers,raw)=http_raw_response(&hr[0]);assert_eq!(status,200);assert_eq!(raw,original);assert_eq!(headers.get("x-imu-session").unwrap(),"native-session");assert_eq!(headers.get("x-imu-nonce").unwrap(),"export-nonce");assert_eq!(headers.get("x-imu-crc32").unwrap(),&crc(&raw));
        handle.call_concurrent(a,&[Val::U32(23),http_path_request("/export",r#"{"kind":"export_session","sid":"../escape","nonce":"n"}"#)],&mut hr).await?;assert_eq!(http_response(&hr[0]).0,400);
        handle.call_concurrent(a,&[Val::U32(23),http_path_request("/export",r#"{"kind":"export_session","sid":"absent","nonce":"n"}"#)],&mut hr).await?;assert_eq!(http_response(&hr[0]).0,404);
        assert_eq!(std::fs::read(&journal)?,original);
        click.call_concurrent(a,&[Val::String("save".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut result).await?;
        click.call_concurrent(a,&[Val::String("prepare".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut result).await?;
        handle.call_concurrent(a,&[Val::U32(23),http_request(r#"{"kind":"native_clock_req","sid":"next-session","seq":0,"nonce":"next","n1_ns":3000000000}"#)],&mut hr).await?;assert_eq!(http_response(&hr[0]).0,200);assert_eq!(std::fs::read(&journal)?,original);
        click.call_concurrent(a,&[Val::String("cancel".into()),Val::Enum("CLICK".into()),Val::String(String::new())],&mut result).await?;
        let before=a.with(|mut s|s.data_mut().sends);
        event.call_concurrent(a,&[Val::Enum("interconnect-message".into()),Val::String(r#"{"p":"J_HELLO1","sid":"late","w1_ms":1792300000000}"#.into())],&mut result).await?;
        assert_eq!(before,a.with(|mut s|s.data_mut().sends));
        handle.call_concurrent(a,&[Val::U32(23),http_request(r#"{"kind":"native_clock_req","sid":"late","seq":0,"nonce":"late","n1_ns":1000}"#)],&mut hr).await?;assert_eq!(http_response(&hr[0]).0,503);
        Ok(())
    }).await??;
    let c=store.data();
    if deny||busy||std::env::args().any(|s|s=="http-denied"){assert_eq!(c.sends,0);assert!(!journal.exists());if busy{assert_eq!(c.http_starts,0);}}
    else if !collision&&!reply_deny{let raw=std::fs::read(&journal)?;let text=std::str::from_utf8(&raw)?;assert_eq!(text.lines().filter(|s|s.contains("\"kind\":\"watch_data\"")).count(),1);assert!(text.contains("watch_data_duplicate"));assert!(text.contains("watch_end"));if c.save_cancelled{assert!(!c.save_finished);assert!(c.saved_bytes.is_empty());}else{assert!(c.save_finished);assert_eq!(c.saved_bytes,raw);}assert_eq!(c.http_stops,1);}
    println!("PASS new HTTP-world WASM: isolated WASI persistence, native and watch sid/nonce binding, CRC blocks, duplicate idempotence, canceled late isolation, system-save byte equality. Mock host only, not Android/BLE/physical sync.");
    Ok(())
}
fn http_request(body:&str)->Val{Val::Record(vec![("method".into(),Val::String("POST".into())),("path".into(),Val::String("/bridge".into())),("query".into(),Val::String(String::new())),("headers".into(),Val::List(vec![])),("body".into(),Val::List(body.bytes().map(Val::U8).collect()))])}
fn http_path_request(path:&str,body:&str)->Val{let mut v=http_request(body);if let Val::Record(fields)=&mut v{for(k,v)in fields{if k=="path"{*v=Val::String(path.into());}}}v}
fn http_raw_response(v:&Val)->(u16,std::collections::BTreeMap<String,String>,Vec<u8>){let Val::Record(fields)=v else{panic!("record")};let mut code=0;let mut headers=std::collections::BTreeMap::new();let mut raw=vec![];for(k,v)in fields{match(k.as_str(),v){("status",Val::U16(n))=>code=*n,("body",Val::List(xs))=>raw=xs.iter().map(|x|if let Val::U8(b)=x{*b}else{panic!("byte")}).collect(),("headers",Val::List(xs))=>for x in xs{if let Val::Record(h)=x{let name=h.iter().find_map(|(k,v)|if k=="name"{if let Val::String(s)=v{Some(s.clone())}else{None}}else{None}).unwrap();let value=h.iter().find_map(|(k,v)|if k=="value"{if let Val::String(s)=v{Some(s.clone())}else{None}}else{None}).unwrap();headers.insert(name,value);}},_=>{}}}(code,headers,raw)}
fn http_empty_response()->Val{Val::Record(vec![("status".into(),Val::U16(0)),("headers".into(),Val::List(vec![])),("body".into(),Val::List(vec![]))])}
fn http_response(v:&Val)->(u16,serde_json::Value){let Val::Record(fields)=v else{panic!("response record")};let mut status=0;let mut body=vec![];for(k,v)in fields{if k=="status"{if let Val::U16(n)=v{status=*n;}}else if k=="body"{if let Val::List(v)=v{body=v.iter().map(|v|if let Val::U8(b)=v{*b}else{panic!("byte")}).collect();}}}(status,serde_json::from_slice(&body).unwrap())}
fn crc(bytes:&[u8])->String{let mut c=0xffffffffu32;for b in bytes{c^=*b as u32;for _ in 0..8{c=(c>>1)^if c&1==1{0xedb88320}else{0};}}format!("{:08x}",!c)}
#[derive(ComponentType,Lift,Lower)]#[component(record)]struct HttpOptions{port:u16,#[component(name="bind-all-interfaces")]bind_all_interfaces:bool}
#[derive(ComponentType,Lift,Lower)]#[component(record)]struct HttpInfo{id:u32,host:String,port:u16,url:String}
use std::sync::Arc;
use tokio::sync::Notify;
impl WasiView for Context{fn ctx(&mut self)->WasiCtxView<'_>{WasiCtxView{ctx:&mut self.wasi,table:&mut self.table}}}
