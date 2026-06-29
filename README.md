🚀 End-to-End Algorithmic Trading & Custom LSM-Tree Database System

📌 Project Overview

A high-performance, event-driven algorithmic trading system built entirely from scratch. This project demonstrates advanced capabilities in Data Engineering, Real-time Streaming, Machine Learning, and Database Internals.

Instead of relying solely on existing frameworks, this system features a custom-built Log-Structured Merge-Tree (LSM-Tree) Database Engine optimized for high-throughput, write-heavy time-series financial data, serving as the core of a real-time Data Lake.

🏗️ System Architecture

The system utilizes a microservices architecture, ensuring high availability, fault tolerance, and minimal latency.

[Binance API] --> [Ingestion Service] 
                         |
                         v
                  [Apache Kafka] (Message Broker)
                         |
      +------------------+------------------+
      |                                     |
      v                                     v
[Live Trading Bot]                 [Data Lake Worker]
(XGBoost + Paper Trading)                   |
                                            v
                              [Custom LSM-Tree Engine]
                              (WAL -> MemTable -> SSTable)


Core Microservices & Components:

Data Ingestion Layer: Fetches raw OHLCV market data from exchange APIs with strict type casting.

Streaming Pipeline (Apache Kafka): Acts as the central nervous system, decoupling data producers from consumers to handle high-frequency market volatility.

Storage Engine (Custom LSM-Tree): A highly efficient database engine built from scratch featuring:

Write-Ahead Log (WAL): Ensures durability against crashes.

MemTable: In-memory data structure for blazing-fast writes.

SSTables & Automated Compaction: Flushes data to disk and periodically merges files to optimize storage.

Bloom Filters: Probabilistic data structures embedded in the read path to prevent expensive and unnecessary disk I/O lookups.

AI Brain (Machine Learning): Real-time feature engineering (RSI, MACD, Bollinger Bands, EMA, ATR) combined with an XGBoost classifier trained on historical data to predict price direction.

Execution Engine: An event-driven paper-trading bot that consumes predictions and executes simulated trades while managing state and risk.

🛠️ Tech Stack

Language: Python 3.11+

Data Streaming: Apache Kafka, Zookeeper

Machine Learning: Scikit-Learn, XGBoost, Pandas, ta (Technical Analysis)

Infrastructure: Docker & Docker Compose

Database Internals: Custom WAL, MemTable, SSTable, Compaction logic, Bloom Filters

📂 Project Structure

algo_trading_system/
├── docker/                      # Docker compose for Kafka & Zookeeper
├── ingestion/                   # API Fetchers & Historical bulk downlaoders
├── ai_brain/                    # Feature engineering, Labeling & ML Pipelines
├── execution_engine/            # Real-time event-driven trading bot
└── storage_engine/              # Custom LSM-Tree Database internals & Data Lake worker


🚀 How to Run (Local Environment)

1. Start the Kafka Cluster:

cd docker
docker-compose up -d


2. Start the Data Ingestion (Producer):
Streams real-time market data into the Kafka topic.

python ingestion/fetcher.py


3. Start the Data Lake Worker (Consumer):
Listens to Kafka and permanently stores data into the custom LSM-Tree database.

python storage_engine/data_lake_worker.py


4. Run the Live Trading Bot (Consumer & Inference):
Extracts real-time features, feeds them into the XGBoost model, and executes paper trades.

python execution_engine/paper_trading_bot.py


(Note: Prior to running the bot, ensure you have trained the XGBoost model using the scripts in ai_brain/ to generate the .pkl file).

⚠️ Disclaimer

This project is for educational and portfolio purposes only. The trading strategies and models provided do not constitute financial advice. Do not use this system with real funds without rigorous testing and risk management.