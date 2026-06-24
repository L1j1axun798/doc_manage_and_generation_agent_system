# 里程碑 4 说明

本阶段新增文件上传、物理存储抽象、`Document` 与 `DocumentVersion`。上传时先校验扩展名和大小，落盘过程中分块计算 SHA-256；数据库写入失败会删除本次已保存的物理文件。新增版本通过锁定 `Document` 行生成递增版本号，并把 `current_version` 指向最新版本。
