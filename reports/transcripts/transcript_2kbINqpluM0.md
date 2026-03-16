# 🎬 YouTube Transcript Analysis

**Video:** [Claude Code Turned Obsidian Into My Dream Second Brain](https://youtu.be/2kbINqpluM0)
**Creator:** Mark Kashef (Early AI Dopters, 68.4K subscribers)
**Duration:** 14:00 | **Words:** 2,896 | **Generated:** 2026-03-15
**Tags:** `obsidian`, `claude code`, `second brain`, `productivity`, `ai`, `vault`, `slash commands`, `cli`, `markdown`, `file processing`, `json canvas`
**Pipeline:** Supadata API → Agent 2 Clean → Agent 3 Summarize → Agent 4 Insight → Agent 5 Report
**Cost:** $0.00

---

## 📋 TL;DR

Mark Kashef demonstrates combining Obsidian (free local markdown note-taking) with Claude Code to build a persistent second brain. After failing 5 times with Obsidian alone, the breakthrough was using Claude Code as the organizational engine. The system uses Obsidian's 95-command CLI, 4 pre-built slash commands (/vault-setup, /daily, /standup, /tldr), a file processing pipeline that compresses PDFs via Gemini Flash into clean markdown, and Kepano's official Obsidian Skills for native vault navigation. Setup takes under 10 minutes.

## 🎯 BidDeed.AI Relevance: 9/10

- CLI-based tooling directly mirrors cli-anything harness architecture
- Slash command pattern directly applicable to /auction-brief, /county-setup, /deal-intel
- File processing pipeline applicable to foreclosure document ingestion
- PDF→markdown pipeline directly applicable to court filings and HOA liens
- Markdown-first approach aligns with GitHub-based documentation strategy
- Vault-as-project pattern applicable to per-county research folders
- Context injection via CLAUDE.md validates our repo-level context approach

## 📖 Chapters

### 1. Introduction — Why Second Brains Fail
Mark explains trying Obsidian 5 times and failing each time until combining it with Claude Code

### 2. What Obsidian Is — Graph View & Vault Tour
Walkthrough of Obsidian's graph view, folder structure, inbox, canvases, markdown files, and search capabilities

### 3. The Bridge — Obsidian CLI + Claude Code
Obsidian's 95-command CLI that Claude Code can onboard itself onto, plus free skills installation

### 4. Installation & Setup
Download links, CLI toggle in settings, and the why behind having one organized place for everything

### 5. The /vault-setup Command
Interactive vault builder that asks 4 questions (role, pain points, scope, existing files) then scaffolds the entire structure

### 6. Slash Commands — /daily, /standup, /tldr
Pre-built commands for daily briefs, project standups, and end-of-session summaries that auto-file to the right folder

### 7. File Processing Pipeline — PDF to Markdown
Taking messy PDFs through a cheap large-context LLM (Gemini) to compress into clean markdown cheat sheets

### 8. Obsidian Skills + JSON Canvas Demo
Using Kepano's official skills for CLI interaction and creating visual canvas maps of processes

### 9. Wrap-Up — Free Starter Kit
Links to setup repo, community, and masterclass for deeper implementation

## 🔑 Key Points

1. Obsidian stores notes as local markdown files — Claude Code reads them natively with zero configuration or API calls
2. The Obsidian CLI exposes 95 commands that Claude Code can self-onboard onto without you learning any of them
3. The /vault-setup slash command asks 4 questions then auto-generates your entire folder structure, CLAUDE.md, and skill files
4. /tldr is the killer command — end any session and it auto-summarizes decisions, next steps, and files to the right folder
5. The file processing pipeline uses a cheap large-context LLM (Gemini Flash, 1M tokens) to compress bulky PDFs into clean markdown cheat sheets
6. Kepano (Obsidian CEO) published official Claude Code skills — obsidian-cli, obsidian-markdown, obsidian-bases, json-canvas
7. JSON Canvas creates visual maps equivalent to Miro/Excalidraw directly inside your vault
8. Context injection via CLAUDE.md means every Claude Code session auto-loads your full vault context globally
9. The entire stack is free: Obsidian ($0) + Claude Code (Max plan) + Gemini API (free tier for file processing)
10. Multiple choice input mode (/vault-setup with ask_user_input tool) removes friction for non-technical users

## 🛠️ Tools & Technologies Mentioned

- **Obsidian** — Free local-first markdown note-taking app with graph view and 95-command CLI
- **Claude Code** — Anthropic's CLI agent that reads, writes, and organizes markdown files directly
- **Obsidian CLI** — 95-command interface for programmatic vault operations — search, create, manage notes
- **Gemini Flash** — Google's free 1M-token-context LLM used for cheap PDF-to-markdown compression
- **JSON Canvas** — Obsidian's visual spatial mapping format for idea boards and process diagrams
- **Kepano's Obsidian Skills** — Official Claude Code skills by Obsidian CEO — obsidian-cli, markdown, bases, canvas
- **/vault-setup** — Interactive command that interviews you then auto-generates folder structure + CLAUDE.md
- **/tldr** — End-of-session command that summarizes decisions and auto-files to correct folder

## 💡 Actionable Takeaways for BidDeed.AI

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | Create /auction-brief slash command | LOW | HIGH |
| 2 | Build /deal-intel foreclosure document pipeline | MEDIUM | HIGH |
| 3 | Implement global CLAUDE.md context injection | LOW | HIGH |
| 4 | Deploy /county-setup for new market expansion | LOW | MEDIUM |
| 5 | Use /tldr for persistent architectural memory | LOW | MEDIUM |
| 6 | Create JSON Canvas for 12-stage pipeline visualization | LOW | LOW |

**Create /auction-brief slash command**
_Direct clone of Mark's /daily pattern. Queries Supabase for upcoming auctions, generates morning briefing with BID/REVIEW/SKIP recommendations. Already deployed to .claude/skills/._

**Build /deal-intel foreclosure document pipeline**
_Mark's PDF→Gemini→markdown pipeline applied to court filings, HOA liens, foreclosure documents. Point at a folder, get structured data with judgment amounts, lien positions, red flags._

**Implement global CLAUDE.md context injection**
_Add BidDeed.AI master context to ~/.claude/CLAUDE.md on every machine. Every Claude Code session anywhere auto-loads full stack knowledge. Already deployed to 5 repos._

**Deploy /county-setup for new market expansion**
_Fork of Mark's /vault-setup pattern. One free-text question about a new Florida county, then auto-generates scraper configs, data source mappings, folder structure. Already deployed._

**Use /tldr for persistent architectural memory**
_End every Claude Code session with /tldr. Auto-captures decisions, discoveries, and next actions to memory.md. Builds cumulative knowledge across sessions without any database._

**Create JSON Canvas for 12-stage pipeline visualization**
_Use Canvas format to visually map Discovery→Scraping→Title→Lien→Tax→Demographics→ML→MaxBid→Decision→Report→Disposition→Archive. Good for investor presentations._

---

## 📝 Full Spoken Transcript (2,896 words)

If you've always wanted to build a second brain, one that you can consistently update and more importantly leverage for all kinds of use cases, then this video is for you. I've personally tried to use a tool called Obsidian five times in my life. Five. And every single time I got the exact same outcome. I'd set it up, I'd organize it, and I'd use it religiously for a whole week. And the week right after, I would forget it even existed. But this changed on the sixth time when I combined Obsidian with Cloud Code. So, in this video, I'm going to show you how you can use this match made in heaven to build the second brain you've always wanted. I'm going to walk you through what it is, what it looks like, how you can set it up, and how you can start getting productivity gains from it today. Let's dive in. All right, so what you're looking at right here is a graph view of all of my thoughts, ideas, and tasks that live in the Obsidian app on my local Mac computer. Now, they have an app for both Windows and Mac, so you should be covered. And if you ever want to be able to take it mobile on the go, they also have a mobile app as well. If you just want to work on it on your desktop, then it's completely free. And if you want to take it on the go and use the cloud, then they do have a small cloud plan if that's of interest to you. And while this has many features, this is probably one of the coolest because if I hover over any one of these bullets, you can see this relates to a Claude skills video section. And related and everything that's adjacent to it is something related semantically to Claude's skills. So you can see that a few of these are existing videos that have already dropped on this channel. And beyond that, at the left hand side, this is where all of our tasks live. Behind the scenes, like I said, Obsidian is just a folder with a series of markdown files. So each one of these are composed of different markdown files categorized in different folders. If you have a brand new idea that doesn't necessarily have a designated home, it can land in the inbox until you, or in this case, cloud code can autocategorize and place it where it fits best. And for all of you notebook LM lovers, they have something called canvases where you can pull up a map in what's called your vault. That's basically the collection of markdown files in this folder. We can go through this which I produced in less than 10 seconds which is a breakdown of different genative AI concepts. So if you do like things like mermaid diagrams, like ask art, it lends itself to this as well. And in terms of the files themselves, they look very similar to something like Notion where you have a series of markdown headers, formatting, [music] the ability to add a date and a tag. And the best part is all of these are now searchable by using their command line interface, which I'll show you in a second with Cloud Code. And when it comes to looking at your graph view, you can not just look at it visibly, but you can also filter it. So you can visually filter the ones that have attachments, have existing files. if you have an orphan task, meaning one that doesn't seem to be connected to any other topic and then you can have different ways to group them and configure them. So this is the app and now I'll show you the bridge to cloud code. So Obsidian has a command line interface. So if you write the word Obsidian after installing it and I'll show you how you can install it, you'll get this beautiful purple logo and then these are all the functionalities, all 95 of the commands. So you can see things here like creating brand new bases, bookmarks, different commands, having daily tasks, deleting everything that you'd need from an API or from a functionality standpoint. And the best part is you don't have to understand how to use the CLI yourself. Claude Code can onboard itself once you've installed it and understand how to leverage each and every functionality. And if you want to make it even easier, I'm going to show you some skills that you can install for free that will make this process of connecting the Cloud Code to your Obsidian Brain that much easier. So to download the app, all you have to do is go to obsidian.mmd/d download. And if you want to download the command line interface, highly recommend to be able to use it effectively. Then you'll go right here. Once you have both installed, you're going to want to go to the very bottom of the general tab of your settings and just make sure that the command line interface accessibility is set to on. So that's the what and the how. But when it comes to the why, the goal is just to have one place where you have different compartments of your life, your business, both that can all live in cohesion where everything's well organized, well documented, and you don't have stale documents. And depending on what you're working on or if you're thinking about something on the go, or if you're brainstorming, each different section of your life also has sub levels or subfolders. And that's where Obsidian can help you out because if you have a personal thing, but there's a certain category for said thing, Claude Code can just listen to you in plain English and it can help designate where this fits best so you can recall it later. Unfortunately for me, this is a cross-section of my brain where it's practically always on fire in every single department. And one thing that I've been awful at my whole life is finding a tool, an app, anything to plant my roots in. So you can name any tool and you'll find it in my graveyard. Whether that's notion, Apple notes, Evernote, to-d doist, bare markdown folders of my own, I've always found a way to lose track of everything. So the appeal here is pretty simple. You have this file cabinet of different markdown files. You can use these markdown files wherever you want on your system because they live on your folder. And then if you want to bring it into a cloud code session, you could literally tell your cloud MD, hey, always refer to insert path of all of these markdown files when I ask you about XYZ. It's so malleable that you could even open a brand new Cloud Code instance in your Obsidian folder if you want to be fully contextualized with each and everything in your life. Now, once you've installed everything, you can layer on these Obsidian skills where if we look at the very bottom here and we zoom in, we have one specifically for leveraging and interacting with the Obsidian CLI, which is basically that dark screen I showed you with all 95 different functionalities. This would give Claude Code a cheat code to leverage them. And if you enjoyed those notebook LM images and diagrams, then this skill would allow you to create those canvases that much more easily. So everything might sound and look good, but you might be asking yourself this very pertinent question. How do I even get started and set up to organize all my thoughts into these folders? Because that time investment alone might be worse than any benefit that you could derive from it. As usual though, I got you covered. So if we pull up a brand new instance of Claude Code, I've created this command called vault setup. And depending on who you are, it will ask you a series of questions. So we're just going to send this over. So it just asks you to tell me about yourself in a few sentences so I can build your vault. Now the prerequisite to getting the most leverage out of this skill is again having the CLI installed so you can actually do things programmatically on your behalf. And the four questions it poses to you are very simple. Number one is what do you do for work? Number two, what falls through the cracks the most? What do you wish you tracked better? Do you want this to be work only or personal life as well? Do you have existing files you want to import? Because this last one is important. If you're a business owner or a company owner, you might have 5, 10, 15 sets of PDFs that you want to be able to distill and somehow bring into your second brain. Now, if you want to remove even more friction, then you can ask the following. [music] Can you ask me all of these questions, but in multiplechoice style format using the ask user input tool? And now you will force Claude Code to give you multiple choice questions to make this as simple as possible. And there you go. You get a series of multiple choice questions. The first one I say that I'm a business owner. Then I say that let's say I want to prioritize projects and decisions and then I want to focus on work and personal or you can do a full life OS. You can always type something of your own. If none of these apply then you can say let's say I want to be able to import PDFs, docs, etc. and then send that over. Then we submit all these answers. And now we give it a better picture of what the structure of our vault should look like. Now obviously if you add some more specificity you'll get more results. And in less than 5 seconds you get this drafted version of your vault where the inbox stays the same but everything else here is configurable. So all of these can be changed depending on what makes sense for you. And if you want to be able to install out of the box some slash commands, my skill gives you that option. So if you want to be able to do a slash command daily to get a daily brief of exactly what's going on in your business, in your life, both, then that's an option. You could do slashstandup for a briefing across projects if you are constantly updating them. And this is my favorite that I use every single day, which is called slashtlddr. So this one is for any conversation. So let's say I'm even building something for my community. I'm vibe coding some form of community app and I'm stuck somewhere or I want to be able to brainstorm something. I will go through a conversation. I will end it with /tlddr. It will create a summary of the last next steps and the next step decisions and I'll store that in Obsidian. And in terms of your PDF, slides, and other files, I do have a pretty elegant solution for you because you most likely don't want to store the raw information that's in there to be always checked and referenced by cloud code. Odds are there's a lot of noise and some signal and we want to be able to harness signal. So I'll also show you my way of handling this as well. So now you could say something like build it and then it will go start cooking. Obviously, it's a lot more helpful to have the CLI and the skills because then you can actually give it the hands and the eyes it needs to go and execute this. Now, in my case, I don't want to overwrite my Obsidian. So, I asked it what it would do next in order so you know exactly how it works in case you want to configure what it does. So, the core things I want you to look at here is number two, which is writing the skill files so that you can leverage them. Writing some form of memory, opening the vault on your computer, asking about context injection. So if you want to start a cloud code session and always globally have certain markdown files injected along with any context in your cloud MD, you can maggyver cloud code to do that. So let's say you've done your initial setup, but you want to take things to the next level and take a folder like this of different types of files, whether they're PDFs, annual reports, JSON files, or Excel files, and find a way to bring that signal from these documents into your second brain. How could you go about doing that? Now, there's no one decisive way, but there is a way that I like to do that's pretty shorthand, pretty cheap, and most importantly, fairly scalable. What I prefer to do is take my messy set of files, then feed it to cloud code, tell it to organize it by file type with different subfolders. Once we do that, we can leverage a cheap API with a very large context window, a million context window that can handle those thick annual reports that can be hundreds of pages long to break that down. step one from a PDF with tons of junk metadata to a markdown file. Then take said markdown file, throw it into a prompt from Gemini that says, "Take a look at this document, synthesize all the salient points, and this is where you would want to intervene and say what those salient points might look like." Once it reads it, synthesizes it, and compresses it, then you're going to have a series of clean markdown files that are all cheat sheets of all of these larger files. And once you have that, now you can use the Obsidian CLI skills that I'll show you right now and plug them in. Once you install the skills, you'll be able to use them by just asking for them or actual slash commands. So if I do Obsidian CLI and I just enter this now, contextually Cloud Code knows that whatever I say next is in reference to my CLI. So I'll say something like this. Can you pull up all the folders we have in the vault called Mark's World? just to show you that functionally it can call out to it. And voila, you can see all the folders that you saw before. Now I can say something like, can we create a canvas using the JSON canvas skill to create a walkthrough of how you would take very large PDF documents, break them down using an LLM, let's say a script from Gemini 3 Flash, a new model, you don't know about it, and then break that down into cheat sheets, and then importing that into Obsidian. So basically I'm asking it to create a canvas of the very process that I just walked through right now. Within a few minutes we load the JSON skill successfully. Then it creates the canvas file. Then it plugs it into our Obsidian and it tells us exactly from left to right what it looks like. So if we just take a peek and go into our Obsidian real quick, this is exactly what it looks like. So it goes through from the large PDF documents to PDF chunker script the three flash API and this is pretty much the exact process I told you about and you can also use this as a miro or skeleadraw equivalent. So this is a very powerful setup and with the CLI and the skills then you're ready to take on anything. So this is everything that you need to set up your second brain of your dreams. So you have the CLI, you have the app, you have the skills and you have the beautiful connection to cloud code to make it all happen. And like I promised, I'll make available to you the Obsidian skills I showed you along with a full guide walking through everything I showed you today and my special vault setup skill completely for free in the second link in the description below. But if you want to go much deeper, see a longer form version of this tutorial, and see exactly how I can execute that pipeline in the middle for file conversion and file synthesis, then you're going to want to check out the first link in the description below. I've even created a turnkey way for anyone to be able to install Obsidian and its dependencies just through a terminal experience exclusively for my members. And to the rest of you, if you found this video helpful, if it opened your mind, maybe your second mind on what is possible with Obsidian and Cloud Code, I would beyond appreciate a like and a comment on the video. helps the video, helps the channel, and I'll see you in the next
