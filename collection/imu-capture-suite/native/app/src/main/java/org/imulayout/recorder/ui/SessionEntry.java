package org.imulayout.recorder.ui;

import java.io.File;
import org.json.JSONObject;
import org.imulayout.recorder.core.Jsons;

/** Reads an existing record without repairing it or certifying experiment quality. */
public final class SessionEntry {
    private static boolean baselineUnavailable(JSONObject report) {
        if(!"unknown_or_fail".equals(report.optString("baseline_stability")))return false;
        for(String k:new String[]{"completion","event_continuity","delivery_continuity","storage_integrity"})if(!"pass".equals(report.optString(k)))return false;
        org.json.JSONArray channels=report.optJSONArray("channels");if(channels==null||channels.length()!=2)return false;
        for(int i=0;i<channels.length();i++){JSONObject c=channels.optJSONObject(i),b=c==null?null:c.optJSONObject("baseline");if(b==null||!Boolean.FALSE.equals(b.opt("valid")))return false;}
        return true;
    }
    public final File directory;
    public final long startWallMs;
    public final String shortId,completionText,qualityText,readWarning,frequencyText;
    public final boolean needsAttention;

    private SessionEntry(File directory,long start,String completion,String quality,String warning,boolean attention,String frequency) {
        this.directory=directory;startWallMs=start;
        String id=directory.getName();shortId=id.substring(0,Math.min(8,id.length()));
        completionText=completion;qualityText=quality;readWarning=warning;needsAttention=attention;frequencyText=frequency;
    }
    public static SessionEntry read(File directory) {
        long start=directory.lastModified();String completion="结束状态未知",quality="检查结果未知",warning="",frequency="请求频率未知";
        boolean attention=false;
        try {
            JSONObject metadata=Jsons.read(new File(directory,"metadata.json"));
            start=metadata.optLong("start_wall_ms",start);
            long period=metadata.optLong("requested_period_us",0),hz=metadata.optLong("requested_rate_hz",0);
            if(period>0)frequency=hz>0?"请求 "+hz+" Hz · "+period+" µs":"请求周期 "+period+" µs";
            String state=metadata.optString("completion_state");
            if(state.equals("complete"))completion="正常结束";
            else if(state.equals("aborted")){completion="未完整结束";attention=true;warning=CompletionMessage.fromMetadata(metadata);}
        } catch(Exception e){completion="信息无法读取";warning="记录信息读取失败；源文件保留，导出时会重新核验。";attention=true;}
        File report=new File(directory,"integrity_report.json");
        if(report.isFile()) {
            try {
                JSONObject result=Jsons.read(report);
                Object passed=result.opt("data_checks_passed");
                if(result.optInt("format_version",-1)==1&&passed instanceof Boolean) {
                    if((Boolean)passed)quality="待独立核验";
                    else if(baselineUnavailable(result)){quality="基线未建立";warning+=(warning.isEmpty()?"":"\n")+"记录已保存；有效的60秒前台基线未建立，持续稳定性待核验。";attention=true;}
                    else {quality="应用检查未通过";attention=true;}
                }
            } catch(Exception e){warning+=(warning.isEmpty()?"":"\n")+"完整性报告读取失败；源文件保留。";attention=true;}
        }
        return new SessionEntry(directory,start,completion,quality,warning,attention,frequency);
    }
}
