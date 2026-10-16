function one(s,a,b){if(s.split(a).length!==2)throw Error('Catalog marker mismatch: '+a.slice(0,100));return s.replace(a,b);}
function page(ux){
 ux=one(ux,'v0.4.3','v0.4.4');
 ux=one(ux,"import research from '../common/research.js'","import research from '../common/research.js'\nimport recordCatalog from '../common/record-catalog.js'");
 ux=one(ux,'this._store=research.createStore(file);','this._catalogGeneration=0;this._store=recordCatalog.wrap(research.createStore(file),file);');
 ux=one(ux,'  renderRecord(){',`  renderRecord(){
    const selected=this._items[this._selection];
    if(selected&&!selected.catalog_ready){
      const generation=++this._catalogGeneration,index=this._selection;this.loading=true;
      this.recordPosition=String(index+1)+' / '+this._items.length;this.recordTitle='会话 '+selected.id.slice(-6);
      this.recordDetail='正在读取当前记录…';this.recordQuality='其它记录按需读取';
      this._store.describe(selected.id).then(item=>{
        if(this._destroyed||generation!==this._catalogGeneration)return;
        this.loading=false;this._items[index]=item;this.renderRecord();
      }).catch(e=>{if(!this._destroyed&&generation===this._catalogGeneration)this.reportError(e);});
      return;
    }`);
 return ux;
}
module.exports={page:page};
