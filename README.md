# Dana-Bot: Automated Multi-Shop RAG Chatbot for Telegram

Dana-Bot is an automated retail assistant designed for Telegram. By leveraging a Retrieval-Augmented Generation (RAG) architecture, the bot interacts with customers, retrieves accurate product details dynamically from a vector store, handles voice message queries, and manages customer sessions across multiple online shops. 

This repository contains the database migrations, ingestion pipelines, and the core chatbot workflow logic required to deploy a production-grade automated support agent.

---

## Business Value and Workload Reduction

In online retail, customer support agents spend a significant amount of time answering repetitive questions regarding product prices, colors, sizes, stock availability, and shipping details. Dana-Bot reduces this operational burden in the following ways:

* **Instant FAQ and Inventory Resolution**: The bot queries an up-to-date vector store to resolve product questions in seconds, deflects high volumes of routine inquiries, and frees support staff to handle complex customer queries.
* **Continuous Availability**: The bot operates 24/7, providing instant assistance to prospective buyers outside business hours.
* **Unified Multi-Shop Support**: A single backend handles distinct shops. Customers can switch between shops using an inline keyboard, and the bot isolates product searches to the selected shop context.
* **Voice Message Support**: Customers can send voice notes. The bot routes them through transcription services and responds with accurate product information, removing the need for agents to manually listen and type responses.

---

## System Architecture

Dana-Bot uses a modular, API-driven stack to perform robust question-answering:

```
                  ┌─────────────────┐
                  │  Telegram Bot   │◄───────── Customer Text / Voice
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ n8n Orchestrator│
                  └────────┬────────┘
                           │
          ┌────────────────┼────────────────┐
          │ (Context Setup)│ (RAG Query)    │ (History Logging)
          ▼                ▼                ▼
┌──────────────────┐ ┌───────────┐ ┌──────────────────┐
│  Supabase DB     │ │ Groq LLM  │ │   Gemini Embed   │
│ - chat_sessions  │ │ (Llama 3) │ │ - Vector Embed   │
│ - chat_history   │ └───────────┘ └──────────────────┘
└──────────────────┘
```

1. **Ingestion Pipeline (`Ingestion.json`)**: Product CSV or text catalogs are parsed, divided into clean chunks, converted into 768-dimensional vector embeddings using the Google Gemini Embedding API (`models/gemini-embedding-001`), and stored inside the Supabase `documents` table.
2. **Text Normalization**: User inputs are normalized to handle Persian and Arabic typographical variants (e.g., converting Arabic Keheh and Yeh characters to Persian variants), ensuring reliable string matches and embedding quality.
3. **Conversational Memory**: The bot retains a short-term memory of the last 3 to 4 turns of the conversation by querying the `chat_history` table in Supabase.
4. **Query Rewriting**: An LLM (`llama-3.3-70b-versatile` hosted on Groq) analyzes the conversational history and rewrites the user's latest query to make it self-contained. For example, if a user asks "Do you have it in blue?", the LLM rewrites it to "Does [Shop Name] have [Product Name] in blue?".
5. **Vector Search**: The rewritten query is embedded and matched against stored product chunks in the Supabase database using cosine similarity. Only matches meeting a similarity threshold of 0.7 are returned.
6. **Response Generation**: The retrieved product contexts are compiled into a prompt, and the Llama 3 model synthesizes a natural, helpful reply in Persian.
7. **Telegram Delivery**: The compiled response is sent back to the customer, and the message exchange is logged to the `chat_history` table.

---

## Database Schema and Migrations

The database is built on PostgreSQL with the `pgvector` extension enabled in Supabase.

### Schema Structure
* **`shops`**: Stores shop meta-information.
  * `shop_id` (UUID, Primary Key)
  * `name` (Text)
* **`documents`**: Stores product details and their vector representations.
  * `id` (BigSerial, Primary Key)
  * `shop_id` (UUID, Foreign Key)
  * `content` (Text, Product descriptions, pricing, options)
  * `embedding` (Vector(768), Dimensional representation of content)
* **`chat_sessions`**: Manages state, active shops, and deferred user queries.
  * `chat_id` (BigInt, Primary Key)
  * `shop_id` (UUID, Nullable)
  * `pending_query` (Text, Nullable)
  * `pending_voice_file_id` (Text, Nullable)
* **`chat_history`**: Records past conversation messages.
  * `id` (BigSerial, Primary Key)
  * `chat_id` (BigInt)
  * `role` (Text, 'user' or 'assistant')
  * `message` (Text)
  * `created_at` (Timestamp with Time Zone)

### Database Functions (RPC)
The system relies on database-level RPC functions to perform state operations safely and efficiently:
* `upsert_pending_query`: Handles transaction logic to cache queries during onboarding or shop selection phases.
* `get_recent_chat_history`: Fetches the last $N$ messages sorted chronologically to pass to the query rewriting engine.
* `match_documents`: Performs a Cosine distance search over the `documents` table filtered by the current `shop_id`.

---

## Installation and Deployment

### 1. Database Setup
1. Create a project in [Supabase](https://supabase.com).
2. Enable the `vector` extension in the Supabase SQL Editor:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Run the SQL statements inside `supabase_migration_cx.sql` to generate the chat tables and RPC functions.
4. (Optional) Run the SQL statements inside `supabase_shops_and_products.sql` to populate sample shops and mock product catalog data.

### 2. Workflow Orchestration (n8n)
1. Import `Chat Bot.json` into a new workflow in your [n8n](https://n8n.io) instance. This represents the primary runtime query engine.
2. Import `Ingestion.json` into a separate workflow in n8n. This serves as your product catalog vector indexing utility.
3. Configure the following API keys and credentials within the n8n nodes:
   * **Telegram Bot Token**: Obtain a bot token via BotFather. Configure the Telegram trigger and HTTP Request nodes using your token.
   * **Gemini API Key**: Obtain a Google AI Studio key. Add the API key parameter to the URL endpoints of the Gemini embedding nodes:
     `https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key=YOUR_GEMINI_API_KEY`
   * **Groq API Credentials**: Set up a Header Auth credential in n8n to connect to the Groq Chat Completions endpoint (`https://api.groq.com/openai/v1/chat/completions`) using your Groq API key:
     * Header Name: `Authorization`
     * Header Value: `Bearer YOUR_GROQ_API_KEY`
   * **Supabase Header Credentials**: Configure Header Auth credentials to connect to your Supabase project endpoints (`https://your-project.supabase.co/rest/v1/...`):
     * Header 1 Name: `apikey`
     * Header 1 Value: `YOUR_SUPABASE_SERVICE_ROLE_KEY`
     * Header 2 Name: `Authorization`
     * Header 2 Value: `Bearer YOUR_SUPABASE_SERVICE_ROLE_KEY`

### 3. Execution Verification
* Use `fix_workflow.py` to inspect the workflow JSON file programmatically, perform structure validations, and configure fallback handlers.
* Send a message to your Telegram bot. If you have no active session, the bot will respond with an inline shop selector. After choosing a shop, you can ask product questions via text or voice.
