const test=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const hash=require('../src/common/ascii-sha256.js').hash;
test('ASCII SHA256 matches Node for standard vectors and every padding boundary',()=>{for(const s of ['', 'abc','hello world',...Array.from({length:200},(_,i)=>'x'.repeat(i)),JSON.stringify([[0,1792590000000,1.25,-2.04,9.8]])])assert.equal(hash(s),crypto.createHash('sha256').update(s,'ascii').digest('hex'));});
test('SHA rejects non-ASCII instead of deleting with guessed encoding',()=>{assert.throws(()=>hash('非ASCII'));});
