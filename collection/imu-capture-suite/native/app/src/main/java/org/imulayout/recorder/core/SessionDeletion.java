package org.imulayout.recorder.core;

import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;

/** Only explicitly confirmed UUID sessions enter the separate deletion directory. */
public final class SessionDeletion {
    interface Cleaner {void clean(Path dir) throws IOException;}
    private final Path app,sessions,pending;
    private final Cleaner cleaner;
    public SessionDeletion(File appFiles) throws IOException {this(appFiles,SessionDeletion::cleanTree);}
    SessionDeletion(File appFiles,Cleaner cleaner) throws IOException {
        app=appFiles.toPath().toRealPath();sessions=app.resolve("sessions");pending=app.resolve("pending-session-deletions");this.cleaner=cleaner;
    }
    private void roots() throws IOException {
        for(Path root:new Path[]{sessions,pending}) {
            if(Files.isSymbolicLink(root))throw new IOException("拒绝链接目录");
            Files.createDirectories(root);
            if(!root.toRealPath().getParent().equals(app))throw new IOException("目录超出应用范围");
        }
    }
    private static boolean uuid(String id){return id!=null&&id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}");}
    private static void inspect(Path dir,Path root) throws IOException {
        Path resolvedRoot=root.toRealPath();
        if(Files.isSymbolicLink(dir)||!Files.isDirectory(dir,LinkOption.NOFOLLOW_LINKS)||!dir.toRealPath().getParent().equals(resolvedRoot))
            throw new IOException("记录不是范围内的直接子目录");
        Files.walkFileTree(dir,new SimpleFileVisitor<Path>() {
            private void check(Path path) throws IOException {
                if(Files.isSymbolicLink(path)||!path.toRealPath().startsWith(resolvedRoot))throw new IOException("记录包含链接或越界路径");
            }
            @Override public FileVisitResult preVisitDirectory(Path path,BasicFileAttributes attrs) throws IOException{check(path);return FileVisitResult.CONTINUE;}
            @Override public FileVisitResult visitFile(Path path,BasicFileAttributes attrs) throws IOException {
                check(path);if(!attrs.isRegularFile())throw new IOException("记录包含非普通文件");return FileVisitResult.CONTINUE;
            }
        });
    }
    public void delete(String id) throws IOException {
        if(!uuid(id))throw new IOException("无效的会话ID");roots();
        Path source=sessions.resolve(id),destination=pending.resolve(id);inspect(source,sessions);
        if(!Files.isRegularFile(source.resolve("manifest.json"),LinkOption.NOFOLLOW_LINKS))throw new IOException("记录尚未封口，不能删除");
        if(Files.exists(destination,LinkOption.NOFOLLOW_LINKS))throw new IOException("同一记录仍有待删除文件，请先重试清理");
        // Both verified absolute paths are direct children in the same private filesystem.
        Files.move(source,destination,StandardCopyOption.ATOMIC_MOVE);
        try{inspect(destination,pending);cleaner.clean(destination);}
        catch(IOException e){throw new IOException("记录已移出列表，但文件尚未清理完成；请重试清理："+e.getMessage(),e);}
    }
    public int retryPending() throws IOException {
        roots();int count=0;
        try(DirectoryStream<Path> entries=Files.newDirectoryStream(pending)) {
            for(Path dir:entries) {
                if(!uuid(dir.getFileName().toString()))throw new IOException("待删除区包含未知项目，未自动删除");
                inspect(dir,pending);cleaner.clean(dir);count++;
            }
        }
        return count;
    }
    public boolean hasPending() throws IOException {
        roots();try(DirectoryStream<Path> entries=Files.newDirectoryStream(pending)){return entries.iterator().hasNext();}
    }
    private static void cleanTree(Path dir) throws IOException {
        Path allowed=dir.toRealPath();
        Files.walkFileTree(dir,new SimpleFileVisitor<Path>() {
            private void remove(Path path) throws IOException {
                if(Files.isSymbolicLink(path)||!path.toRealPath().startsWith(allowed))throw new IOException("清理路径校验失败");
                Files.delete(path);
            }
            @Override public FileVisitResult visitFile(Path path,BasicFileAttributes attrs) throws IOException{remove(path);return FileVisitResult.CONTINUE;}
            @Override public FileVisitResult postVisitDirectory(Path path,IOException error) throws IOException {
                if(error!=null)throw error;remove(path);return FileVisitResult.CONTINUE;
            }
        });
    }
}
