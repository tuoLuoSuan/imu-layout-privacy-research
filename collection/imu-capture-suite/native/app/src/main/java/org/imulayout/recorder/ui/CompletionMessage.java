package org.imulayout.recorder.ui;

import org.json.JSONObject;

/** Presents saved facts only; never retries or changes completion/quality decisions. */
public final class CompletionMessage {
    private CompletionMessage() {}
    private static String text(String value) { return value==null?"":value.trim(); }

    public static String format(boolean abnormal,String failure,String error,String bridgeStatus) {
        if(!abnormal)return "已保存，可导出；连续性结论请查看完整性报告";
        String reason=text(failure),detail=text(error),bridge=text(bridgeStatus);
        String explanation;
        switch(reason) {
            case "joint_bridge_failed":explanation="本机连接中断";break;
            case "joint_bridge_thread_not_closed":explanation="本机连接尚未退出";break;
            case "joint_event_write_failed":explanation="联机事件写入失败";break;
            case "wake_lock_coverage_lost":explanation="连续运行条件中断";break;
            case "queue_overflow":explanation="写入缓冲不足";break;
            case "visibility_condition_failed":explanation="采集通知条件不满足";break;
            case "drain_timeout":explanation="记录收尾超时";break;
            case "start_failure":explanation="采集初始化失败";break;
            case "process_end_unknown":explanation="应用退出前的结束状态未确认";break;
            default:explanation=reason.isEmpty()?"具体停止原因未记录":"采集发生异常（"+reason+"）";
        }
        if(detail.isEmpty()&&reason.startsWith("joint_")&&!bridge.isEmpty()&&!bridge.equals("not_started"))detail=bridge;
        return "未完整结束："+explanation+"\n"+(detail.isEmpty()?"":"原因："+detail+"\n")+"部分记录已保留，可导出";
    }

    public static String fromMetadata(JSONObject metadata) {
        String reason=text(metadata.optString("stop_failure",""));
        if(reason.isEmpty())reason=metadata.optString("stopped_reason","");
        String detail=text(metadata.optString("start_error",""));
        if(detail.isEmpty())detail=metadata.optString("storage_error","");
        return format(!"complete".equals(metadata.optString("completion_state","")),reason,detail,metadata.optString("joint_bridge_status",""));
    }
}
