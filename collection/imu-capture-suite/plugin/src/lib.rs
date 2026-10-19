pub mod protocol;
#[cfg(feature="astrobox")]
mod host;
#[cfg(feature="astrobox")]
pub mod bindings {
    wit_bindgen::generate!({path:"wit",world:"psys-world-v4-http",generate_all,pub_export_macro:true,default_bindings_module:"crate::bindings"});
}
