"""Plan-1 交接项四：三张空表补齐设计文档要求的不变式。

Revision ID: 0016
Revises: 0015

为什么现在做：三张表在 fip_dev 实测均为 0 行。EXCLUDE USING gist 要建索引、
部分唯一索引要全表扫，空表上几乎免费；有数据之后成本高一个量级，而且
一旦已经存在重叠区间，迁移会直接失败并卡住整条链。

btree_gist：EXCLUDE 里的 `fund_id WITH =` / `manager_id WITH =` 用的是
btree 的等值操作符，而 GiST 索引默认不认识 bigint 的 `=`。缺这个扩展时
CREATE 会报 `data type bigint has no default operator class for access
method "gist"` —— 报得很响，不会静默，但必须先建。

daterange 的边界写成 '[)'：valid_to 是【开区间右端】（与 interval_check
的 valid_from < valid_to 一致），写成默认的 '[]' 会把「前一段 8-01~8-15、
后一段 8-15~9-01」这种首尾相接的合法交接判成重叠。valid_to IS NULL 时
daterange 得到无上界区间，正是「至今仍在任」的正确语义。

排他键含 manager_id（裁定 PF-6）：退化成 `EXCLUDE (fund_id WITH =,
range WITH &&)` 会直接拒收合法的共管数据（同一基金同期多位经理）。
带上 manager_id 之后排他的是「同一经理对同一基金的任职区间重叠」，
共管不受影响，因此本仓库不需要 role='LEAD' 这类部分约束、也不需要 role 列。

本迁移只建约束与索引，不动任何列、不动任何数据（C-12）。
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.execute(
        "ALTER TABLE fund.fund_manager_assignment "
        "ADD CONSTRAINT ex_fma_no_overlap EXCLUDE USING gist ("
        "fund_id WITH =, manager_id WITH =, "
        "daterange(valid_from, valid_to, '[)') WITH &&)"
    )
    op.execute(
        "CREATE INDEX idx_fma_manager_valid_from "
        "ON fund.fund_manager_assignment (manager_id, valid_from)"
    )
    op.execute(
        "CREATE INDEX idx_fma_fund_valid_from "
        "ON fund.fund_manager_assignment (fund_id, valid_from)"
    )

    # 与 0014 的 uq_pfi_open_interval 逐字同形（含 WHERE 子句），
    # ORM 侧 postgresql_where 必须一模一样。
    op.execute(
        "CREATE UNIQUE INDEX uq_fund_fee_open_interval "
        "ON fund.fund_fee (share_class_id, fee_type) "
        "WHERE valid_to IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_fsh_open_interval "
        "ON fund.fund_status_history (share_class_id) "
        "WHERE valid_to IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX fund.uq_fsh_open_interval")
    op.execute("DROP INDEX fund.uq_fund_fee_open_interval")
    op.execute("DROP INDEX fund.idx_fma_fund_valid_from")
    op.execute("DROP INDEX fund.idx_fma_manager_valid_from")
    op.execute(
        "ALTER TABLE fund.fund_manager_assignment DROP CONSTRAINT ex_fma_no_overlap"
    )
    # 【不】DROP EXTENSION btree_gist：它是库级对象，别的迁移或将来的表
    # 可能已经依赖它，回滚一支迁移不该顺手拆掉共享地基。
