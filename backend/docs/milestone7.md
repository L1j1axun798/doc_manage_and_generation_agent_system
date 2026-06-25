# 里程碑 7 说明

本阶段新增 `TemporaryAccessGrant`，用于生成限时限次的临时下载 Token。创建接口只在响应中返回一次明文 Token，数据库仅保存 HMAC-SHA256 哈希；公开下载接口只能通过 Token 下载指定 `DocumentVersion`，不能搜索或枚举资料。

Token 消费通过事务和 `select_for_update()` 锁定授权记录，校验撤销、过期和剩余次数后递增 `used_count`。下载成功、拒绝、撤销和物理文件缺失都会写入审计。

本阶段不实现公开搜索、批量下载、通知或部署能力。
