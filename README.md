# Multilingual AI Chatbot 

A full-stack AI chat application powered by the Google Gemini API. This platform features dynamic language adaptation, secure OAuth authentication, and a cloud-synced admin workspace for data management.

##  Core Features
* **Adaptive AI Engine:** Integrates Gemini 2.5 Flash for high-speed, context-aware responses with custom system instructions.
* **Regional Code-Switching:** Automatically adapts to local dialects and Latin-script regional languages based on user cadence and input.
* **Secure Authentication:** Implements Google OAuth for secure user onboarding and a hardened manual login system for admin access.
* **Persistent Cloud Storage:** Manages chat history and user interactions using a hosted PostgreSQL database to survive ephemeral server reboots.

## Tech Stack
* **Backend:** Python, Flask, SQLAlchemy, OAuthlib
* **AI Provider:** Google GenAI SDK (Gemini 2.5 Flash)
* **Database:** Supabase (PostgreSQL)
* **Deployment & Hosting:** Render (Web Service)

##  Security & Architecture
Built with production-grade security practices to ensure data integrity:
* Strict separation of configuration and code using `.env` for secrets management.
* OAuth email restriction and secured session cookies to prevent session hijacking.



   GOOGLE_CLIENT_ID="your_oauth_id"
   GOOGLE_CLIENT_SECRET="your_oauth_secret"
   DATABASE_URL="your_supabase_url"
