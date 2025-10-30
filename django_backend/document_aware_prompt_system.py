"""
文档感知的 Prompt 系统
强制关联文档 1 规则，提供精准的技术错误分析
"""

import logging
from typing import Dict, List, Any, Optional
from c_minus_error_analyzer import CMinusErrorAnalyzer, ErrorCategory

logger = logging.getLogger(__name__)


class DocumentAwarePromptSystem:
    """文档感知的 Prompt 系统"""
    
    def __init__(self):
        self.analyzer = CMinusErrorAnalyzer()
    
    def build_prompt(self, query: str, context: List[Dict] = None) -> str:
        """构建文档感知的 Prompt"""
        # 检测是否是技术错误
        if self._is_technical_error(query):
            return self._build_technical_error_prompt(query, context)
        else:
            return self._build_general_prompt(query, context)
    
    def _is_technical_error(self, query: str) -> bool:
        """检测是否是技术错误"""
        technical_keywords = [
            "lexical", "syntax", "error", "compilation", "token", 
            "vector store", "rag", "retrieval failed", "float", 
            "identifier", "词法", "编译", "检索"
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in technical_keywords)
    
    def _build_technical_error_prompt(self, query: str, context: List[Dict] = None) -> str:
        """构建技术错误分析 Prompt"""
        # 使用 CMinusErrorAnalyzer 分析
        analysis = self.analyzer.analyze_error(query)
        prompt = self.analyzer.build_prompt(query)
        
        # 如果有上下文日志，添加日志参考
        if context:
            log_context = self._build_log_context(context)
            prompt = f"{prompt}\n\n## 相关历史日志参考\n{log_context}"
        
        return prompt
    
    def _build_general_prompt(self, query: str, context: List[Dict] = None) -> str:
        """构建通用分析 Prompt"""
        base_prompt = """你是资深的系统分析专家，具备深厚的技术分析经验。你的任务是基于提供的信息，进行精准的技术分析。

## 分析要求
1. **精准性**：准确对应技术细节，避免泛化描述
2. **关联性**：若问题涉及 C--，仅可引用《智能数据分析任务书》文档 1.1/1.2 的具体条款，不得引用通用 C/C++ 规则
3. **可操作性**：提供可直接执行的解决方案
4. **验证性**：提供验证修复效果的具体方法

## 禁止事项
- 禁止输出与文档 1.1/1.2 无关的泛化建议（如“定期检查”“养成习惯”）
- 禁止建议使用 C/C++ 的 f/F 后缀或指数记号（如 36f、36e2）

## 输出格式
请使用 Markdown 三级标题格式输出：

### 问题分析
[详细分析问题]

### 原因分析
[分析根本原因]

### 解决方案
[提供具体、可执行的解决步骤]

### 验证步骤
[提供验证方法]
"""
        
        # 添加日志上下文
        if context:
            log_context = self._build_log_context(context)
            base_prompt = f"{base_prompt}\n\n## 相关历史日志参考\n{log_context}"
        
        base_prompt = f"{base_prompt}\n\n## 当前需要分析的问题\n{query}\n\n请开始分析："
        
        return base_prompt
    
    def _build_log_context(self, context: List[Dict]) -> str:
        """构建日志上下文"""
        if not context:
            return "暂无相关日志数据"
        
        log_context = ""
        for i, log in enumerate(context, 1):
            content = log.get('content', '')
            score = log.get('score', 0)
            log_context += f"**日志 {i}** (相似度: {score:.3f})\n{content}\n\n"
        
        return log_context


# 全局实例
document_aware_prompt_system = DocumentAwarePromptSystem()
