package org.imulayout.recorder.core;

import java.util.UUID;

/** Process-local ownership across Activity recreation and worker threads. */
public final class OperationGate {
    public static final OperationGate SESSIONS=new OperationGate();
    private Lease owner;
    public synchronized Lease tryAcquire() {
        if(owner!=null)return null;
        owner=new Lease();return owner;
    }
    public synchronized boolean isHeld(){return owner!=null;}
    public synchronized Lease find(String id){return owner!=null&&owner.id.equals(id)?owner:null;}
    public final class Lease {
        private final String id=UUID.randomUUID().toString();
        public String id(){return id;}
        public void release(){synchronized(OperationGate.this){if(owner==this)owner=null;}}
    }
}
