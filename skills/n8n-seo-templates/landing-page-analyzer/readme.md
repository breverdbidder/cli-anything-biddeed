# AI-Powered Landing Page CRO Analyzer

This workflow acts as a specialized Conversion Rate Optimization (CRO) agent that conducts a comprehensive audit of any landing page. By combining **Firecrawl** for high-fidelity scraping, **OpenAI** for structural text analysis, and **Google Gemini** for visual design critique, this tool synthesizes a professional audit report and delivers it directly to your email.

It evaluates pages based on expert principles such as Radical Clarity, Cognitive Load, and Visual Hierarchy, providing a strategic blueprint to improve conversion rates.

![n8n-landing-page-analyzer-banner](n8n-landing-page-analyzer.png)

## Key Features

*   **Multi-Modal Analysis:** Unlike standard text analyzers, this workflow uses **Google Gemini Pro** to "see" the landing page via a screenshot, allowing it to critique design, whitespace, and visual hierarchy alongside the copy.
*   **Full-Page Scraping:** Utilizes **Firecrawl** to capture both the raw markdown content and a full-page screenshot of the target URL.
*   **Structured Element Extraction:** Uses **OpenAI (GPT-4.1 Mini)** to parse the page and isolate critical elements like the Hero Headline, Value Proposition, Credibility Statements, and Call-to-Action (CTA) microcopy.
*   **Expert CRO Framework:** The AI evaluates the page against specific principles:
    *   **Radical Clarity:** Can the offer be understood in 5 seconds?
    *   **Singular Focus:** Is the path to conversion distraction-free?
    *   **Cognitive Load:** Does the design prioritize function over form?
    *   **Multi-Faceted Trust:** Are there sufficient credibility signals?
*   **Automated HTML Reporting:** Generates a beautifully styled, mobile-responsive HTML email report containing observations, actionable recommendations, and the analyzed screenshot.

## Prerequisites

Before you begin, ensure you have the following accounts and credentials set up. This workflow relies on several external services to perform the audit.

1.  **Firecrawl API Key:** Required for scraping the website content and generating the full-page screenshot.
2.  **OpenAI API Key:** Used for the initial text parsing and structure extraction (tested with GPT-4.1 Mini).
3.  **Google Gemini API Key:** Used for the visual analysis and final report synthesis (tested with Gemini 2.5 Pro).
4.  **Gmail Account:** Required to send the final report via email.

## How to use it

1.  **Import the Workflow:** Download the workflow JSON file and import it into your n8n instance.
2.  **Configure Credentials:** Add your API keys for Firecrawl, OpenAI, Google Gemini, and Gmail to the corresponding nodes.
3.  **Launch the Form:** The workflow starts with a Form Trigger.
4.  **Submit a Request:** Enter the **URL** of the landing page you want to audit and the **Email Address** where you want to receive the report.
5.  **Receive the Audit:** The agent will crawl the site, analyze the data, and send a comprehensive HTML report to your inbox.

## How it works (Technical Flow)

1.  **Input:** User submits URL via n8n Form.
2.  **Scrape:** Firecrawl fetches Markdown and Screenshot.
3.  **Text Parse:** OpenAI extracts key marketing copy (Headlines, CTAs).
4.  **Visual Synthesis:** Google Gemini receives the JSON + The Screenshot.
5.  **Formatting:** A Code node transforms the JSON analysis into a styled HTML template.
6.  **Delivery:** Gmail sends the HTML body with the screenshot attached.
