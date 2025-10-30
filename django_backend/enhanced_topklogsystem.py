"""
增强型 TopKLogSystem - 集成智能 Prompt 系统
基于原有的 TopKLogSystem，集成增强型 Prompt 设计
"""

import os
import re

# chroma 不上传数据
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["DISABLE_TELEMETRY"] = "1"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

import json
import logging
import pandas as pd
from typing import Any, Dict, List

# langchain
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_ollama import OllamaLLM, OllamaEmbeddings

# llama-index & chroma
import chromadb
from llama_index.core import Settings  # 全局
from llama_index.core import Document
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore  # 注意导入路径

# 导入增强型 Prompt 系统
from enhanced_prompt_system import EnhancedPromptSystem
from c_minus_error_analyzer import CMinusErrorAnalyzer

# 日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedTopKLogSystem:
    """增强型 TopKLogSystem，集成智能 Prompt 系统"""
    
    def __init__(
            self,
            log_path: str,
            llm: str,
            embedding_model: str,
    ) -> None:
        # init models
        self.embedding_model = OllamaEmbeddings(model=embedding_model)
        self.llm = OllamaLLM(model=llm, temperature=0.1)

        # init database
        Settings.llm = self.llm
        Settings.embed_model = self.embedding_model  # 全局设置

        self.log_path = log_path
        self.log_index = None
        self.vector_store = None
        
        # 初始化增强型 Prompt 系统
        self.prompt_system = EnhancedPromptSystem()
        
        self._build_vectorstore()  # 直接构建

    # 加载数据并构建索引
    def _build_vectorstore(self):
        vector_store_path = "./data/vector_stores"
        os.makedirs(vector_store_path, exist_ok=True)  # exist_ok=True 目录存在时不报错

        chroma_client = chromadb.PersistentClient(path=vector_store_path)  # chromadb 持久化

        # ChromaVectorStore 将 collection 与 store 绑定
        # 也是将 Chroma 包装为 llama-index 的接口
        # StorageContext存储上下文， 包含 Vector Store、Document Store、Index Store 等
        log_collection = chroma_client.get_or_create_collection("log_collection")

        # 构建 log 库 index
        log_vector_store = ChromaVectorStore(chroma_collection=log_collection)
        log_storage_context = StorageContext.from_defaults(vector_store=log_vector_store)
        if log_documents := self._load_documents(self.log_path):
            self.log_index = VectorStoreIndex.from_documents(
                log_documents,
                storage_context=log_storage_context,
                show_progress=True,
            )
            logger.info(f"日志库索引构建完成，共 {len(log_documents)} 条日志")

    @staticmethod
    # 加载文档数据
    def _load_documents(data_path: str) -> List[Document]:
        if not os.path.exists(data_path):
            logger.warning(f"数据路径不存在: {data_path}")
            return []

        documents = []
        for file in os.listdir(data_path):
            ext = os.path.splitext(file)[1]
            if ext not in [".txt", ".md", ".json", ".jsonl", ".csv"]:
                continue

            file_path = f"{data_path}/{file}"
            try:
                if ext == ".csv":  # utf-8 的 csv
                    # 大型 csv 分块进行读取
                    chunk_size = 1000  # 每次读取1000行
                    for chunk in pd.read_csv(file_path, chunksize=chunk_size):
                        for row in chunk.itertuples(index=False):  # 无行号
                            content = str(row).replace("Pandas", " ")
                            documents.append(Document(text=content))
                else:  # .txt or .md, .json
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        doc = Document(text=content, )
                        documents.append(doc)
            except Exception as e:
                logger.error(f"加载文档失败 {file_path}: {e}")
        return documents

        # 检索相关日志

    def retrieve_logs(self, query: str, top_k: int = 10) -> List[Dict]:
        if not self.log_index:
            return []

        try:
            retriever = self.log_index.as_retriever(similarity_top_k=top_k)  # topK
            results = retriever.retrieve(query)

            formatted_results = []
            for result in results:
                formatted_results.append({
                    "content": result.text,
                    "score": result.score
                })
            return formatted_results
        except Exception as e:
            logger.error(f"日志检索失败: {e}")
            return []

            # LLM 生成响应

    def generate_response(self, query: str, context: Dict) -> str:
        prompt = self._build_enhanced_prompt(query, context)  # 使用增强型 Prompt

        try:
            response = self.llm.invoke(prompt)  # 调用LLM
            return response
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return f"生成响应时出错: {str(e)}"

    def _build_enhanced_prompt(self, query: str, context: Dict) -> List[Dict]:
        """构建增强型 Prompt"""
        try:
            # 强化岔路口：命中 C-- 词法/技术错误 → 使用 Analyzer
            ql = (query or "").lower()
            is_lexical = (
                ("lexical analysis failed" in ql) or
                ("mismatched float literal" in ql) or
                ("nearby source" in ql and "float" in ql) or
                ("float literal" in ql) or
                (" 36.;" in ql or '"36.;"' in ql)
            )
            logger.info(f"DEBUG MESSAGE: ql contains lexical? {is_lexical}")
            if is_lexical:
                logger.info("DEBUG MESSAGE: ---> 检测到C--词法/技术错误，调用 CMinusErrorAnalyzer！（EnhancedTopKLogSystem）")
                analyzer = CMinusErrorAnalyzer()
                prompt_text = analyzer.build_prompt(query)

                system_message = SystemMessagePromptTemplate.from_template(prompt_text)
                user_message = HumanMessagePromptTemplate.from_template("""
请严格依照上述条款与步骤作答，禁止给出与文档 1.1/1.2 无关的泛化建议。
""")
                prompt = ChatPromptTemplate.from_messages([system_message, user_message])
                return prompt.format_prompt().to_messages()

            # 使用增强型 Prompt 系统（并做后置净化）
            enhanced_prompt = self.prompt_system.build_enhanced_prompt(query, context)
            enhanced_prompt = self._sanitize_prompt_text(enhanced_prompt)

            system_message = SystemMessagePromptTemplate.from_template(enhanced_prompt)
            user_message = HumanMessagePromptTemplate.from_template("""
请基于以上分析框架和上下文信息，对问题进行深入分析。
""")
            prompt = ChatPromptTemplate.from_messages([system_message, user_message])
            return prompt.format_prompt().to_messages()
            
        except Exception as e:
            logger.error(f"增强型 Prompt 构建失败: {e}")
            # 回退到基础实现
            return self._build_fallback_prompt(query, context)

    def _sanitize_prompt_text(self, text: str) -> str:
        """对非 Analyzer 路径的提示文本进行后置净化，统一课程要求。"""
        if not isinstance(text, str):
            return text
        sanitized = text
        # 将单行 'flex && gcc' 改为三行标准命令
        sanitized = re.sub(r"flex\s+lexer\.l\s*&&\s*gcc\s+lex\.yy\.c\s*-o\s+lexer(?:\s*\S+)?",
                           "flex lexer.l\ngcc lex.yy.c -o lexer",
                           sanitized, flags=re.IGNORECASE)
        # 统一运行命令与扩展名为 .c--
        sanitized = re.sub(r"\./lexer\s+[^\s`\n]+",
                           "./lexer your_test_file.c--  # 确认输出中无 <ERROR>",
                           sanitized)
        sanitized = sanitized.replace("your_test_file.c", "your_test_file.c--")
        sanitized = sanitized.replace("test_fix.c", "test_fix.c--")
        # 去除可能的 f/F 建议（保守替换常见示例）
        sanitized = sanitized.replace("36f", "36.0").replace("36F", "36.0")
        # 若没有代码块，则附加标准命令块（幂等）
        if "flex lexer.l\ngcc lex.yy.c -o lexer" in sanitized and "./lexer your_test_file.c--" in sanitized and "```bash" not in sanitized:
            block = """```bash
flex lexer.l
gcc lex.yy.c -o lexer
./lexer your_test_file.c--  # 确认输出中无 <ERROR>
```"""
            sanitized += ("\n\n" + block)
        return sanitized

    def _build_fallback_prompt(self, query: str, context: Dict) -> List[Dict]:
        """回退到基础 Prompt 实现"""
        # 系统消息 - 定义角色和任务
        system_message = SystemMessagePromptTemplate.from_template("""
你是故障日志诊断专家，需基于提供的历史日志上下文和用户问题，生成详细分析报告。
报告需包含：1. 故障描述；2. 可能原因；3. 解决方案（分步骤说明）；4. 预防建议。
分析需结合历史日志中的相似案例，确保建议可落地。
        """)

        # 构建日志上下文
        log_context = "## 相关历史日志参考:\n"
        for i, log in enumerate(context, 1):
            log_context += f"日志 {i} : {log['content']}\n"

        # 用户消息
        user_message = HumanMessagePromptTemplate.from_template(""" 
            {log_context} 
            ## 当前需要分析的问题: 
            {query} 

            请基于以上信息，提供详细的分析报告: 
        """)

        # 创建提示词
        prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])

        return prompt.format_prompt(
            log_context=log_context,
            query=query
        ).to_messages()

        # 执行查询

    def query(self, query: str) -> Dict:
        log_results = self.retrieve_logs(query)
        response = self.generate_response(query, log_results)  # 生成响应

        return {
            "response": response,
            "retrieval_stats": len(log_results)
        }

    # 示例使用


if __name__ == "__main__":
    # 初始化系统
    system = EnhancedTopKLogSystem(
        log_path="./data/log",
        llm="deepseek-r1:7b",
        embedding_model="bge-large:latest"
    )

    # 执行查询
    query = "如何解决数据库连接池耗尽的问题？"
    result = system.query(query)

    print("查询:", query)
    print("响应:", result["response"])
    print("检索统计:", result["retrieval_stats"])
