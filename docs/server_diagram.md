# gptme Server V2 API Architecture

## Overall Architecture

```mermaid
flowchart TD
    %% Client
    Client[Web Client]

    %% API Layer
    Client <--> API[V2 API Endpoints]

    %% Main Server Components
    subgraph "Server"
        API --> SessionManager[Session Manager]
        API --> LogManager[Log Manager]
        API --> GenerationManager[Generation]
        API --> ToolManager[Tool Management]

        SessionManager -- Manages --> Sessions[(Active Sessions)]
        Sessions -- Contains --> EventQueues[Event Queues]
        Sessions -- Tracks --> PendingTools[Pending Tools]

        LogManager -- Stores --> Files[(JSONL Files)]

        %% Generation Flow
        GenerationManager -- Triggers --> GenerationThread[Generation Thread]
        GenerationThread -- Calls --> LLM[LLM API]
        GenerationThread -- Detects --> PendingTools
        GenerationThread -- Emits --> GenEvents[Generation Events]
        GenerationThread -- Stores --> LogManager

        %% Tool Flow
        ToolManager -- Processes --> ToolActions[Tool Actions]
        ToolActions -- Confirm --> ToolExecution[Tool Execution]
        ToolActions -- Edit --> ToolExecution
        ToolActions -- Skip --> ToolSkipped[Tool Skipped]
        ToolExecution -- Emits --> ToolEvents[Tool Events]
        ToolExecution -- Stores --> LogManager
        ToolExecution -- Resumes --> GenerationThread

        %% Event System
        GenEvents --> EventQueues
        ToolEvents --> EventQueues
    end

    %% Event Stream
    API -- SSE --> EventStream[Event Stream]
    EventQueues --> EventStream
    EventStream --> Client

    %% Tool States
    subgraph "Tool States"
        direction LR
        Pending((Pending)) --> Executing((Executing))
        Pending --> Skipped((Skipped))
        Executing --> Completed((Completed))
        Executing --> Failed((Failed))
    end

    %% Event Types
    subgraph "Event Types"
        direction TB
        Connected[connected]
        MessageAdded[message_added]
        GenStarted[generation_started]
        GenProgress[generation_progress]
        GenComplete[generation_complete]
        ToolPending[tool_pending]
        ToolExecuting[tool_executing]
        ToolOutput[tool_output]
        ToolFailed[tool_failed]
        ToolSkipped[tool_skipped]
    end
```

## Tool Confirmation Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as V2 API
    participant Session as Session Manager
    participant GenThread as Generation Thread
    participant LLM
    participant ToolExec as Tool Execution
    participant LogManager

    Client->>API: POST /conversations/:id/generate
    API->>Session: Create/Get Session
    API->>GenThread: Start Generation
    GenThread->>LLM: Stream Tokens
    LLM-->>GenThread: Token Stream
    GenThread-->>Session: Send Generation Progress Events
    Session-->>Client: SSE: generation_progress events

    GenThread->>GenThread: Detect Tool
    GenThread->>LogManager: Store Assistant Message
    GenThread->>Session: Create Tool Pending Event
    Session-->>Client: SSE: tool_pending event

    Client->>API: POST /conversations/:id/tool/confirm
    API->>Session: Get Tool & Action
    API->>ToolExec: Execute Tool
    ToolExec->>Session: Send Tool Executing Event
    Session-->>Client: SSE: tool_executing event

    ToolExec->>ToolExec: Execute Command
    ToolExec->>LogManager: Store Tool Output
    ToolExec->>Session: Send Tool Output Event
    Session-->>Client: SSE: tool_output event

    ToolExec->>GenThread: Resume Generation
    GenThread->>LLM: Stream Tokens
    LLM-->>GenThread: Token Stream
    GenThread-->>Session: Send Generation Progress Events
    Session-->>Client: SSE: generation_progress events

    GenThread->>LogManager: Store Final Assistant Message
    GenThread->>Session: Send Generation Complete Event
    Session-->>Client: SSE: generation_complete event
```

## Key Components

### Session Management
- **SessionManager**: Central class that manages all active sessions
- **ConversationSession**: Represents a client connection to a conversation
- **Event Queues**: Track events for each session to be sent via SSE

### Tool Processing
- **Tool States**: Tools go through various states (pending, executing, completed, failed, skipped)
- **Tool Actions**: Clients can confirm, edit, skip, or auto-confirm tools
- **Tool Execution**: Happens in background threads to avoid blocking

### Event System
- **Server-Sent Events (SSE)**: Real-time event stream to clients
- **Event Types**: Various event types for different stages of processing
- **Event Queue**: Per-session queue of events to be sent to clients
