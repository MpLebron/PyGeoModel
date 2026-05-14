# PyGeoModel 论文修改待办清单

基于 CEUS 期刊 (Manuscript Number: CEUS-D-25-01800) 审稿意见整理

---

## 代码/技术修复

- [ ] 1. 修复PyPI上的GitHub链接 (setup.py中的url字段) `[高优先级]`
- [ ] 2. API密钥外部化，使用环境变量替代硬编码 `[高优先级]`
- [ ] 3. 添加pytest测试框架和测试用例 `[高优先级]`
- [ ] 4. 增加类型注解和docstring文档

## 文档完善

- [ ] 5. 在README中说明OpenGMS是否开源、与PyGeoModel的关系
- [ ] 6. 添加每个模型的参数说明文档（start_time, end_time, DEM header等）
- [ ] 7. 说明查询的学术知识库是哪个（Consensus API）

## 案例/可复现性修复

- [ ] 8. 确保mybinder案例能完整运行并产生可验证结果 `[高优先级]`
- [ ] 9. 为案例提供预期输出结果作为对照
- [ ] 10. 测试并修复AirSpeed、Kinematic Wave等模型的问题

## 论文内容修改

### 图表修正

- [ ] 11. 修复Figure 2拼写错误 'Snippests' → 'Snippets' `[R1]`
- [ ] 12. Figure 2中添加GeoPandas `[R1]`

### 核心问题回应

- [ ] 13. 明确论文定位：科学论文还是软件论文，补充研究问题 `[R1]` `[高优先级]`
- [ ] 14. 明确目标用户群体（研究者 vs 规划师） `[R2]`
- [ ] 15. 解释为何在Jupyter中使用GUI而非纯代码 `[R2]`
- [ ] 16. 解释为何不做QGIS插件 `[R2]`
- [ ] 21. 明确PyGeoModel相对于OpenGMS的独立贡献 `[R1+R2]` `[高优先级]`

### 技术描述修正

- [ ] 17. Figure 9补充Stage 1和Stage 2的prompts说明 `[R1]`
- [ ] 18. 修正Section 4.2中invoke_model与suggest_model的调用顺序描述 `[R1]`
- [ ] 19. 说明PyGeoModel如何保证透明性和可复现性 `[R2]`
- [ ] 20. 说明是否支持代码方式直接调用Model Class（而非GUI） `[R2]`

### 文字精简

- [ ] 22. 精简Section 1引言的引用数量 `[R2]`
- [ ] 23. 精简Section 2.1关于Jupyter的描述 `[R2]`
- [ ] 24. 删除Section 2.2与引言的重复内容 `[R2]`
- [ ] 25. 删除Section 3中主观性的赞美用词 `[R2]`

## 项目成熟度

- [ ] 26. 增加更多commits和开发历史
- [ ] 27. 邀请合作者贡献代码，增加contributor

---

## 优先处理事项

1. **#1** - 修复PyPI GitHub链接（立即可做）
2. **#8** - mybinder案例可复现性（审稿人明确指出无法复现）
3. **#13** - 明确论文定位（根本性问题）
4. **#21** - PyGeoModel vs OpenGMS的贡献区分（两位审稿人都提到）

---

## 审稿人原文参考

### Reviewer #1 主要意见

- GitHub link broken on PyPI
- Unclear boundary between PyGeoModel and OpenGMS
- Missing prompts for Stage 1 and Stage 2
- Cannot reproduce results on mybinder
- Project maturity issues (3 months, 10 commits, single author)

### Reviewer #2 主要意见

- Unclear target users
- Why GUI for code-based Jupyter?
- Transparency and reproducibility concerns
- What's PyGeoModel's contribution vs OpenGMS?
- Excessive references in introduction
