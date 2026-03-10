"""数据库模型定义文件.

所有模型继承 AbstractBaseModel，使用雪花ID主键和软删除机制。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.base import (
    AbstractBaseModel,
    BeijingTimeZone,
    StringifiedBigInt,
    register_model,
)
from app.utils.snowflake_id import generate_id

# ==================== 用户模块 ====================


@register_model
class UserModel(AbstractBaseModel):
    """用户表（users）。.

    存储所有注册用户的基本信息。
    """

    __tablename__ = "users"

    # 主键 ID，使用雪花算法生成，避免暴露自增ID和分布式ID冲突
    id: Mapped[str] = mapped_column(
        StringifiedBigInt, default=generate_id, primary_key=True, comment="雪花ID主键"
    )

    username: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="登录用户名（可为手机号）"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希值（加盐加密）"
    )
    phone: Mapped[str] = mapped_column(
        String(50), unique=True, comment="手机号（用于找回密码）"
    )
    status: Mapped[int] = mapped_column(
        Integer, default=2, index=True, comment="状态：1-正常，0-禁用，2-待审核"
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True, comment="是否为管理员（true/false）"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="最后登录时间"
    )

    logs: Mapped[list["UserLogModel"]] = relationship(
        "UserLogModel",
        primaryjoin="and_(UserModel.id==UserLogModel.user_id, UserLogModel.user_id.isnot(None))",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ==================== 系统日志与配置 ====================


@register_model
class UserLogModel(AbstractBaseModel):
    """用户日志表（user_logs）。.

    记录用户的日志。
    """

    __tablename__ = "user_logs"

    # 主键 ID，使用雪花算法生成，避免暴露自增ID和分布式ID冲突
    id: Mapped[str] = mapped_column(
        StringifiedBigInt, default=generate_id, primary_key=True, comment="雪花ID主键"
    )

    user_id: Mapped[None | str] = mapped_column(
        StringifiedBigInt,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="操作用户ID",
    )
    action: Mapped[None | str] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="操作类型：login, recharge, consume 等",
    )
    ip_address: Mapped[None | str] = mapped_column(
        String(45),
        nullable=True,
        index=True,
        comment="用户IP地址（IPv4/IPv6）",
    )
    user_agent: Mapped[None | str] = mapped_column(Text, comment="浏览器/客户端信息")
    level: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="日志级别: INFO, WARNING, ERROR等",
    )
    message: Mapped[None | str] = mapped_column(
        Text,
        comment="日志消息",
    )

    # 关联关系
    user: Mapped[Optional["UserModel"]] = relationship(
        "UserModel", back_populates="logs", lazy="selectin"
    )


@register_model
class SystemLogModel(AbstractBaseModel):
    """系统操作日志表（system_logs）。.

    记录关键操作行为，用于审计与排查。
    """

    __tablename__ = "system_logs"

    # 主键 ID，使用雪花算法生成，避免暴露自增ID和分布式ID冲突
    id: Mapped[str] = mapped_column(
        StringifiedBigInt, default=generate_id, primary_key=True, comment="雪花ID主键"
    )

    action: Mapped[None | str] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="操作类型：login, recharge, consume 等",
    )
    level: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="日志级别: INFO, WARNING, ERROR 等",
    )
    message: Mapped[None | str] = mapped_column(Text, comment="日志消息")


@register_model
class CanvasModel(AbstractBaseModel):
    """画布表 (canvas) - 存储画布的基础元数据"""

    __tablename__ = "canvas"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt, default=generate_id, primary_key=True, comment="雪花ID主键"
    )
    user_id: Mapped[str] = mapped_column(
        StringifiedBigInt,
        index=True,
        nullable=False,
        comment="关联创建该画布的用户ID（逻辑外键）",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="画布名称")
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="画布的详细介绍"
    )
    location: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="画布文件夹路径"
    )
    default_canvas_parmas: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="默认画布配置"
    )


@register_model
class DefaultCanvasRuleModel(AbstractBaseModel):
    """画布配置默认表 (default_canvas_rules)"""

    __tablename__ = "default_canvas_rules"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt, default=generate_id, primary_key=True, comment="雪花ID主键"
    )
    default_canvas_parmas: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="全局默认的画布配置"
    )


# ==================== 节点与规则配置模块 ====================


@register_model
class CanvasNodeRuleModel(AbstractBaseModel):
    """画布节点配置表 (canvas_node_rule) - 特定画布的节点默认行为"""

    __tablename__ = "canvas_node_rule"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt, default=generate_id, primary_key=True, comment="雪花ID主键"
    )
    canvas_id: Mapped[str] = mapped_column(
        StringifiedBigInt,
        index=True,
        nullable=False,
        comment="关联的画布ID（逻辑外键）",
    )
    node_type: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="绑定的节点类型"
    )
    default_model_params: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="默认使用的模型及参数"
    )
    default_node_params: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="节点表单的其他默认参数"
    )


@register_model
class DefaultCanvasNodeRuleModel(AbstractBaseModel):
    """画布节点默认配置表 (default_canvas_node_rule) - 全局基础的节点默认配置"""

    __tablename__ = "default_canvas_node_rule"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt, default=generate_id, primary_key=True, comment="雪花ID主键"
    )
    node_type: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="绑定的节点类型"
    )
    default_model_params: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="默认使用的模型及参数"
    )
    default_node_params: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="节点表单的其他默认参数"
    )


# ==================== 工作流与节点实例模块 ====================


@register_model
class NodeModel(AbstractBaseModel):
    """节点表 (node) - 画布上的具体节点实例"""

    __tablename__ = "node"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt, default=generate_id, primary_key=True, comment="雪花ID主键"
    )
    canvas_id: Mapped[str] = mapped_column(
        StringifiedBigInt, index=True, nullable=False, comment="所属画布ID（逻辑外键）"
    )
    node_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="节点类型"
    )
    measured: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="节点尺寸信息"
    )
    position: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="节点在画布上的坐标"
    )
    prompt: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="节点提示词"
    )
    resource_ids: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="节点资源列表"
    )
    model_params: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default={}, comment="记录的模型及其参数"
    )
    node_params: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default={}, comment="除模型外的节点参数配置"
    )
    status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default="idle",
        comment="节点状态(idle/running/completed)",
    )
    group_id: Mapped[Optional[str]] = mapped_column(
        StringifiedBigInt, index=True, nullable=True, comment="所属组ID（逻辑外键）"
    )
    created_by: Mapped[str] = mapped_column(
        StringifiedBigInt, index=True, nullable=False, comment="创建人ID（逻辑外键）"
    )


@register_model
class NodeConnectionModel(AbstractBaseModel):
    """节点关系表 (node_connection) - 节点间的连线"""

    __tablename__ = "node_connection"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt,
        default=generate_id,
        primary_key=True,
        comment="连线唯一标识雪花ID",
    )
    canvas_id: Mapped[str] = mapped_column(
        StringifiedBigInt, index=True, nullable=False, comment="所属画布ID（逻辑外键）"
    )
    source: Mapped[str] = mapped_column(
        StringifiedBigInt, index=True, nullable=False, comment="起点节点ID（逻辑外键）"
    )
    target: Mapped[str] = mapped_column(
        StringifiedBigInt, index=True, nullable=False, comment="终点节点ID（逻辑外键）"
    )
    deletable: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=True, comment="当前连线是否可删除"
    )
    selectable: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=True, comment="当前连线是否可选择"
    )
    connection_type: Mapped[str] = mapped_column(
        String(50), default="default", nullable=True, comment="连线类型"
    )


@register_model
class ConnectionRuleModel(AbstractBaseModel):
    """可连线的节点规则表 (connection_rule) - 限制哪些节点可以相连"""

    __tablename__ = "connection_rule"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt,
        default=generate_id,
        primary_key=True,
        comment="规则唯一标识雪花ID",
    )
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="起点节点类型"
    )
    target_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="终点节点类型"
    )
    relation_rule_type: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="关系规则类型(text_to_image等)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="规则是否启用"
    )


@register_model
class GroupModel(AbstractBaseModel):
    """组表 (group) - 画布上的节点成组"""

    __tablename__ = "group"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt,
        default=generate_id,
        primary_key=True,
        comment="组唯一标识雪花ID",
    )
    canvas_id: Mapped[str] = mapped_column(
        StringifiedBigInt, index=True, nullable=False, comment="所属画布ID（逻辑外键）"
    )
    created_by: Mapped[str] = mapped_column(
        StringifiedBigInt, nullable=False, comment="创建人ID（逻辑外键）"
    )
    layour_type: Mapped[str] = mapped_column(
        String(50),
        default="horizontal",
        nullable=True,
        comment="布局类型(horizontal/grid)",
    )
    title: Mapped[str] = mapped_column(
        String(255), default="新建组", nullable=True, comment="组名称"
    )
    measured: Mapped[dict] = mapped_column(JSON, nullable=False, comment="组尺寸信息")
    position: Mapped[dict] = mapped_column(JSON, nullable=False, comment="组位置信息")
    is_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=True, comment="是否为通过模版生成"
    )


# ==================== 模板、任务与日志模块 ====================


@register_model
class WorkflowTemplateModel(AbstractBaseModel):
    """工作流模版表 (workflow_template)"""

    __tablename__ = "workflow_template"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt, default=generate_id, primary_key=True, comment="模版雪花ID"
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="模板名称")
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="模板描述"
    )
    created_by: Mapped[str] = mapped_column(
        StringifiedBigInt, nullable=False, comment="创建用户ID（逻辑外键）"
    )
    dag_data: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="以DAG的形式存储画布上的节点"
    )


@register_model
class TaskModel(AbstractBaseModel):
    """任务节点执行记录表 (task)"""

    __tablename__ = "task"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt,
        default=generate_id,
        primary_key=True,
        comment="任务唯一标识雪花ID",
    )
    canvas_id: Mapped[str] = mapped_column(
        StringifiedBigInt, index=True, nullable=False, comment="所属画布ID（逻辑外键）"
    )
    model_params: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="当前任务所使用的模型参数"
    )
    retry_count: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, nullable=True, comment="当前重试次数"
    )
    max_retries: Mapped[Optional[int]] = mapped_column(
        Integer, default=3, nullable=True, comment="最大重试次数"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        BeijingTimeZone(), nullable=True, comment="任务开始时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        BeijingTimeZone(), nullable=True, comment="任务完成时间"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        comment="状态(pending/running/success/failed)",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="错误消息"
    )
    result: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="执行结果"
    )


@register_model
class ActionLogModel(AbstractBaseModel):
    """操作日志表 (action_log) - 用于重放操作或协同广播"""

    __tablename__ = "action_log"

    id: Mapped[str] = mapped_column(
        StringifiedBigInt,
        default=generate_id,
        primary_key=True,
        comment="操作日志雪花ID",
    )
    canvas_id: Mapped[str] = mapped_column(
        StringifiedBigInt, index=True, nullable=False, comment="所属画布ID（逻辑外键）"
    )
    action_by: Mapped[str] = mapped_column(
        StringifiedBigInt, index=True, nullable=False, comment="操作人ID（逻辑外键）"
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="操作类型(create/update/delete)"
    )
    target: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="目标类型(node/connection/group)"
    )
    payload: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="操作请求的负载数据"
    )
