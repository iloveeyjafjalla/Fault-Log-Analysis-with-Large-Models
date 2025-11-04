# 工作记录（Prompt/RAG 升级）

更新时间：2025-11-04

## 当前状态
- 文档感知、岔路口分流（词法/语法/语义/RAG）、RAG 混合检索（向量+可选 BM25）、MMR、可选 Cross-Encoder 重排、证据编号与统一三行命令输出均已上线并验证。

## 本次更新
- 统一运行命令注释：强制第三行为 `./lexer your_test_file.c--  # 确认输出中无 <ERROR>`。
- 折叠并去重命令来源：删除叙述/内联命令与多余 ```markdown 代码块，最终仅保留一个三行 bash 代码块。
- 归一任何 `./lexer ...` 目标为 `.c--`，去除 `$` 提示符。
- 移除“验证步骤”叙述段，避免与代码块重复。

## 已完成（概览）
- 分流：`enhanced_topklogsystem.py` 命中 lexical/syntax/semantic 关键词走 `CMinusErrorAnalyzer`；非分析器路径做统一净化。
- 分析器：`c_minus_error_analyzer.py` 支持词法/语法/语义/RAG 专用 Prompt 与修复逻辑。
- RAG：`enhanced_topklogsystem.py` 启用 MMR；`reranker.py` 可选 Cross-Encoder；`bm25_index.py` 可选 BM25 稀疏召回（缺依赖自动回退）。
- Prompt：`enhanced_prompt_system.py` 输出“证据 N”，强制仅引用证据。
- 文档：`TECHNICAL_DOCUMENTATION.md` 增补语法/语义章节与示例；流程与规范对齐。

## 测试指引
- 触发技术错误用例，后端应打印：
  - `DEBUG MESSAGE: ql contains special? True`
  - `命中技术错误分支，调用 CMinusErrorAnalyzer！`
- 前端仅出现：
```bash
flex lexer.l
gcc lex.yy.c -o lexer
./lexer your_test_file.c--  # 确认输出中无 <ERROR>
```

## 待办（Next Steps，按优先级）
1) 查询改写（QueryExpander）
- 目标：提升召回全面性（同义/扩展/分面查询），合并去重后再重排。
- 实施：新增 `query_expander.py`（可选开启、短缓存）；`enhanced_topklogsystem.retrieve_logs` 合并改写结果。

2) 入库与知识扩充（Ingest）
- 目标：满足“本地知识较少→补充专业知识”的要求。
- 实施：新增 `scripts/ingest.py` 完成清洗/层级切块/元数据；`_load_documents` 支持子目录；建议新增 `data/knowledge/`。

3) 稀疏检索增强（BM25/ES）
- 目标：稳定的稀疏通道与字段权重、分域（章节/来源）过滤。
- 实施：可接入 Elasticsearch（或继续增强 `bm25_index.py`），支持按 `section/source/lang` 过滤与加权。

4) 证据溯源与可视化
- 目标：老师关注“更精准的数据分析”与可核查性；增加来源显示。
- 实施：为 `Document` 注入 `metadata={'source': file_path, 'section': ...}`；在“证据 N”行尾追加 `[来源: 文件名/章节]`。

5) 自动评估与回归
- 目标：量化相关性/可用性提升（与老师要求对齐）。
- 实施：新增评测脚本（nDCG/MRR/Recall@K、引用一致性检查），固定种子与用例，提交评测表。

6) 运行依赖提示与一键脚本（可选）
- 目标：便于开启重排/稀疏通道。
- 实施：在 README/WORKLOG 增加依赖提示与 `make setup-rag`（安装 `sentence-transformers`、`rank-bm25`）。

## 备注
- 若老师优先要求“检索相关性”提升，优先推进 1)+3)；若要求“知识覆盖”，优先推进 2)。
