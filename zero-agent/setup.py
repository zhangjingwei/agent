#!/usr/bin/env python3
"""
Setup script for Universal Agent MVP
"""

from setuptools import setup, find_packages

setup(
    name="zero-agent",
    version="0.1.0",
    description="Nexus Agent - Universal AI Agent Framework",
    author="R&D Team",
    author_email="hi@zhangjingwei.com",
    packages=find_packages(include=["tools*", "api*", "sdk*", "scripts*", "llm*", "orchestration*", "core*", "config*"]),
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "httpx>=0.25.0",
        "python-dotenv>=1.0.0",
        "structlog>=23.2.0",
        "aiofiles>=23.2.0",
        "langchain==0.2.17",
        "langchain-core==0.2.43",
        "langchain-openai==0.1.25",
        "langchain-anthropic==0.1.23",
        "langgraph==0.2.58",
        "langgraph-checkpoint-sqlite==2.0.1"
    ],
    entry_points={
        'console_scripts': [
            'start=scripts.start:main',
        ],
    },
    python_requires=">=3.9",
)
