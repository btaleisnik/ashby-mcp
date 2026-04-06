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

#### Single client

If you only have one Ashby API key, use the standard `ASHBY_API_KEY` variable:

```json
{
    "mcpServers": {
        "ashby": {
            "command": "uvx",
            "args": [
                "--from",
                "git+https://github.com/btaleisnik/ashby-mcp",
                "ashby"
            ],
            "env": {
                "ASHBY_API_KEY": "YOUR_ASHBY_API_KEY"
            }
        }
    }
}
```

#### Multiple clients

To switch between multiple Ashby accounts, use named keys with the `ASHBY_API_KEY_<NAME>` pattern:

```json
{
    "mcpServers": {
        "ashby": {
            "command": "uvx",
            "args": [
                "--from",
                "git+https://github.com/btaleisnik/ashby-mcp",
                "ashby"
            ],
            "env": {
                "ASHBY_API_KEY_CLIENTNAME": "your-key",
                "ASHBY_API_KEY_OTHERCLIENT": "your-other-key"
            }
        }
    }
}
```

Replace `CLIENTNAME` / `OTHERCLIENT` with whatever names make sense for your clients. The name after `ASHBY_API_KEY_` is what you'll use to select the client.

When multiple keys are configured, a `select_client` tool will appear in the MCP. You'll be prompted to pick a client before making any API calls — or you can just tell Claude which client you want to work with and it'll handle it.

### Claude Code Setup

If you use Claude Code in the terminal, add your keys to a `.env` file in the project root:

```
# Single client
ASHBY_API_KEY=your-key

# Or multiple clients
ASHBY_API_KEY_CLIENTNAME=your-key
ASHBY_API_KEY_OTHERCLIENT=your-other-key
```

After saving, restart Claude Desktop or Claude Code for the changes to take effect.

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
