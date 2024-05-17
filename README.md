## Zelin Accounting

Zelin Accounting

功能
1. 中国资产负债表
  - 资产负债表设置
  - 资产负债表

2. 中国利润表
  - 利润表设置
  - 利润表

3. 中国现金流量表（直接法）
  - 现金流量编码
  - 现金流量表

4. 物料移动原因代码
  - 原因代码
  - 物料需求
  - 物料移动

5. 制造费用差异结算（工单入库成品成本追溯调整）

6. 公司主数据设置默认工单入库生产成本-材料，生产成本-结转科目

7. 委外入库成品明细取委外采购订单明细（委外加工费物料）加工费科目（暂估委外加工费科目），只适用于15版

8. 采购和销售发票税费明细允许手工输入实际税额，并将差异调至公司主数据中的小数精度(圆整)尾差科目

9. 已出库待开票明细报表
  - 合并多张销售出库(明细)下推一张销售发票
  - 合并正常出库与退货单(明细)下推一张销售发票

10. 库存暂估对账报表

11. 会计凭证支持负数借贷金额，需在中国会计设置中启用此功能
  - 标准功能会基于借货净值自动切换借货方向
  - 此功能支持以下几种场景借货方负数(红字冲销)
    - 日记账凭证
    - 基于源发票下推的退款采购与销售发票

12. 未开票销售出库/采购入库退货隐藏下推发票与退款按钮
- 基于销售出库的销售退货，在源销售出库未开票情况下，退货数量会被更新到源销售出库，退货单的退款金额已被源销售出库扣减(冲抵), 被退货单未开票情况下，退货单的开票由被退货单处理，标准功能未处理这个细节，导致退货单与被退货单都可下推发票，退货金额被处理两次。采购入库同理。

12. 列表界面勾选多张总帐凭证打印，逻辑修改为每个原始凭证（源单据）生成多行总帐凭证，只用其中一个总帐凭证打印该原始凭证的多行总帐凭证

13. 销售订单多种税率，即物料税费模板，基于系统内的json内容的物料税率提取税率赋值给含税价隐藏字段用于打印输出

14. 销售出库开票状态基于出库单价*开票数量(标准为开票金额)，需在中国会计设置中启用出库单开票数量状态控制

15. 销售订单与采购订单下推付款时默认付款金额基于预付百分比(付款条款明细中到期日小于等于当天）而非整个订单金额

16. 物料价格启用阶梯价，需在中国会计设置中勾选启用

17. 打印日志, 每次打印预览系统自动记录一条打印日志，需在中国会计设置中勾选启用

#### License

MIT