# MCP Ashby Connector

A Model Context Protocol (MCP) server implementation for Ashby integration, allowing LLMs to interact with Ashby's Applicant Tracking System (ATS) data and operations.

## Features

Provides **full coverage of the Ashby API** (~137 endpoints) by dynamically generating MCP tools from the bundled OpenAPI spec. Supported categories include:

- **Candidates** - create, search, list, update, anonymize, notes, tags, projects, file/resume uploads
- **Applications** - create, list, update, transfer, stage changes, source changes, hiring team management
- **Application Feedback** - list and submit feedback scorecards
- **Jobs** - create, search, list, update, set status, compensation management
- **Job Postings** - info, list, update
- **Interviews** - info, list, schedules (create, update, cancel), events, plans, stages
- **Interviewer Pools** - create, list, update, archive/restore, add/remove users
- **Offers** - create, info, list, update, start
- **Openings** - create, list, search, update, add/remove jobs and locations, state management
- **Custom Fields** - create, info, list, set values
- **Departments** - create, info, list, update, archive/restore, move
- **Locations** - create, info, list, update (address, name, workplace type, remote status), archive/restore, move
- **Surveys** - form definitions, requests, submissions
- **Users** - info, list, search, interviewer settings
- **Webhooks** - create, update, delete
- **And more** - API key info, archive reasons, assessments, approvals, candidate tags, close reasons, communication templates, feedback form definitions, file info, hiring team roles, job boards, job templates, projects, referrals, sources, source tracking links

## How It Works

The server parses the bundled `openapi.json` (Ashby's OpenAPI 3.1 spec) at startup and auto-generates an MCP tool for each endpoint. This means:

- Adding new Ashby endpoints only requires updating `openapi.json` - no code changes needed
- Tool names map directly to API paths (e.g., `/candidate.create` becomes `candidate_create`)
- Input schemas are extracted and resolved from the OpenAPI spec, including pagination parameters

## Configuration

### Claude Desktop Setup

To connect this MCP server to Claude Desktop, add the configuration below to your `claude_desktop_config.json`.

**Config file location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

#### Option 1: Install from PyPI (recommended)

```json
{
    "mcpServers": {
        "ashby": {
            "command": "uvx",
            "args": [
                "--from",
                "mcp-ashby-connector",
                "ashby"
            ],
            "env": {
                "ASHBY_API_KEY": "YOUR_ASHBY_API_KEY"
            }
        }
    }
}
```

#### Option 2: Run from a local clone

```json
{
    "mcpServers": {
        "ashby": {
            "command": "uv",
            "args": [
                "--directory",
                "/absolute/path/to/ashby-mcp",
                "run",
                "ashby"
            ],
            "env": {
                "ASHBY_API_KEY": "YOUR_ASHBY_API_KEY"
            }
        }
    }
}
```

Replace `/absolute/path/to/ashby-mcp` with the actual path to your cloned repository.

---

Replace `YOUR_ASHBY_API_KEY` with your Ashby API key. After saving the config, restart Claude Desktop for the changes to take effect.

## Project Structure

```
src/
  ashby/
    server.py      # MCP server - dynamically generates tools from OpenAPI spec
    openapi.json   # Ashby OpenAPI 3.1 spec (source of truth for all endpoints)
```

## Dependencies

The project requires the following Python packages:
- mcp
- requests
- python-dotenv
