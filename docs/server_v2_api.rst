V2 Server API
=============

Overview
--------

The V2 API is a new, more powerful API for gptme that provides better control flow, tool confirmation, and improved state management. It is designed to be used alongside the existing API, with endpoints available under the ``/api/v2/`` prefix.

Key improvements:

- Session-based architecture for better state management
- Separate event stream for different types of events
- Tool confirmation workflow
- Better interruption handling
- More predictable behavior

Concepts
--------

Sessions
~~~~~~~~

A session represents a client's connection to a conversation. Multiple clients can connect to the same conversation simultaneously, each with their own session. Sessions track:

- Active generations
- Pending tool executions
- Client connection status

Events
~~~~~~

The V2 API uses Server-Sent Events (SSE) to stream updates to clients. Events include:

- ``connected``: Initial connection established
- ``message_added``: A new message was added to the conversation
- ``generation_started``: Model generation has started
- ``generation_progress``: Token-by-token updates during generation
- ``generation_complete``: Generation has completed
- ``tool_pending``: A tool use has been detected and is awaiting confirmation
- ``tool_executing``: A tool is currently executing
- ``tool_output``: Output from a tool execution
- ``tool_failed``: A tool execution failed
- ``tool_skipped``: A tool execution was skipped
- ``interrupted``: The generation was interrupted
- ``error``: An error occurred
- ``ping``: Keep-alive message

Tool Confirmation
~~~~~~~~~~~~~~~~

The V2 API allows clients to confirm, edit, skip, or auto-confirm tool uses before they are executed. This provides greater control and safety.

Endpoints
---------

Conversations
~~~~~~~~~~~~

.. http:get:: /api/v2/conversations

   List available conversations.

   **Example response**:

   .. sourcecode:: json

      [
        {
          "id": "conversation-123",
          "name": "My Conversation",
          "created_at": "2023-06-01T12:00:00Z"
        }
      ]

.. http:get:: /api/v2/conversations/(string:conversation_id)

   Get details of a specific conversation.

   **Example response**:

   .. sourcecode:: json

      {
        "id": "conversation-123",
        "name": "My Conversation",
        "created_at": "2023-06-01T12:00:00Z",
        "log": [
          {
            "role": "user",
            "content": "Hello, world!",
            "timestamp": "2023-06-01T12:00:00Z"
          }
        ]
      }

.. http:put:: /api/v2/conversations/(string:conversation_id)

   Create a new conversation.

   **Example request**:

   .. sourcecode:: json

      {
        "messages": [
          {
            "role": "system",
            "content": "You are an AI assistant.",
            "timestamp": "2023-06-01T12:00:00Z"
          }
        ]
      }

   **Example response**:

   .. sourcecode:: json

      {
        "status": "ok",
        "conversation_id": "conversation-123",
        "session_id": "session-abc"
      }

.. http:post:: /api/v2/conversations/(string:conversation_id)

   Add a message to a conversation.

   **Example request**:

   .. sourcecode:: json

      {
        "role": "user",
        "content": "Hello, world!"
      }

   **Example response**:

   .. sourcecode:: json

      {
        "status": "ok"
      }

Sessions
~~~~~~~~

.. http:post:: /api/v2/conversations/(string:conversation_id)/session

   Create a new session for a conversation.

   **Example response**:

   .. sourcecode:: json

      {
        "status": "ok",
        "session_id": "session-abc"
      }

Events
~~~~~~

.. http:get:: /api/v2/conversations/(string:conversation_id)/events

   Subscribe to events for a conversation.

   **Parameters**:

   - ``session_id``: Session ID (optional, will create a new session if not provided)

   **Example event stream**:

   .. sourcecode:: text

      data: {"type": "connected", "session_id": "session-abc"}

      data: {"type": "message_added", "message": {"role": "user", "content": "Hello", "timestamp": "2023-06-01T12:00:00Z"}}

      data: {"type": "generation_started"}

      data: {"type": "generation_progress", "token": "H"}

      data: {"type": "generation_progress", "token": "e"}

      data: {"type": "generation_progress", "token": "l"}

      data: {"type": "generation_progress", "token": "l"}

      data: {"type": "generation_progress", "token": "o"}

      data: {"type": "generation_complete", "message": {"role": "assistant", "content": "Hello", "timestamp": "2023-06-01T12:00:05Z"}}

Generation
~~~~~~~~~~

.. http:post:: /api/v2/conversations/(string:conversation_id)/generate

   Start generating a response.

   **Example request**:

   .. sourcecode:: json

      {
        "session_id": "session-abc",
        "model": "openai/gpt-4o"
      }

   **Example response**:

   .. sourcecode:: json

      {
        "status": "ok",
        "message": "Generation started",
        "session_id": "session-abc"
      }

.. http:post:: /api/v2/conversations/(string:conversation_id)/interrupt

   Interrupt the current generation.

   **Example request**:

   .. sourcecode:: json

      {
        "session_id": "session-abc"
      }

   **Example response**:

   .. sourcecode:: json

      {
        "status": "ok",
        "message": "Interrupted"
      }

Tool Confirmation
~~~~~~~~~~~~~~~~

.. http:post:: /api/v2/conversations/(string:conversation_id)/tool/confirm

   Confirm, edit, skip, or auto-confirm a tool execution.

   **Example request (confirm)**:

   .. sourcecode:: json

      {
        "session_id": "session-abc",
        "tool_id": "tool-123",
        "action": "confirm"
      }

   **Example request (edit)**:

   .. sourcecode:: json

      {
        "session_id": "session-abc",
        "tool_id": "tool-123",
        "action": "edit",
        "content": "ls -la"
      }

   **Example request (skip)**:

   .. sourcecode:: json

      {
        "session_id": "session-abc",
        "tool_id": "tool-123",
        "action": "skip"
      }

   **Example request (auto-confirm)**:

   .. sourcecode:: json

      {
        "session_id": "session-abc",
        "tool_id": "tool-123",
        "action": "auto",
        "count": 5
      }

   **Example response**:

   .. sourcecode:: json

      {
        "status": "ok",
        "message": "Tool confirmed"
      }

Testing the V2 API
-----------------

The V2 API includes comprehensive tests to ensure functionality works as expected:

.. code-block:: bash

   # Run all server tests including V2 API tests
   pytest tests/test_server_v2.py -v

   # Run a specific V2 API test
   pytest tests/test_server_v2.py::test_v2_generate -v

   # Manual interactive testing
   python scripts/test_v2_api.py

   # Test with tool usage
   python scripts/test_v2_api.py --tool-test

   # Test against a specific server
   python scripts/test_v2_api.py --url http://localhost:8080

Client Implementation Example
----------------------------

Here's a simple JavaScript example demonstrating how to use the V2 API in a web client:

.. code-block:: javascript

   class GptmeClient {
     constructor(baseUrl) {
       this.baseUrl = baseUrl;
       this.sessionId = null;
       this.conversationId = null;
       this.eventSource = null;
     }

     async createConversation() {
       const response = await fetch(`${this.baseUrl}/api/v2/conversations/my-conversation`, {
         method: 'PUT',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({
           messages: [{
             role: 'system',
             content: 'You are an AI assistant.',
             timestamp: new Date().toISOString()
           }]
         })
       });

       const data = await response.json();
       this.conversationId = data.conversation_id;
       this.sessionId = data.session_id;

       return data;
     }

     async sendMessage(content) {
       await fetch(`${this.baseUrl}/api/v2/conversations/${this.conversationId}`, {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({
           role: 'user',
           content
         })
       });
     }

     async generate() {
       await fetch(`${this.baseUrl}/api/v2/conversations/${this.conversationId}/generate`, {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({
           session_id: this.sessionId
         })
       });
     }

     async confirmTool(toolId, action, content) {
       const body = {
         session_id: this.sessionId,
         tool_id: toolId,
         action
       };

       if (action === 'edit') {
         body.content = content;
       } else if (action === 'auto') {
         body.count = 5; // Auto-confirm next 5 tools
       }

       await fetch(`${this.baseUrl}/api/v2/conversations/${this.conversationId}/tool/confirm`, {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify(body)
       });
     }

     async interrupt() {
       await fetch(`${this.baseUrl}/api/v2/conversations/${this.conversationId}/interrupt`, {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({
           session_id: this.sessionId
         })
       });
     }

     subscribeToEvents(callbacks) {
       if (this.eventSource) {
         this.eventSource.close();
       }

       this.eventSource = new EventSource(
         `${this.baseUrl}/api/v2/conversations/${this.conversationId}/events?session_id=${this.sessionId}`
       );

       this.eventSource.onmessage = (event) => {
         const data = JSON.parse(event.data);

         switch (data.type) {
           case 'connected':
             if (callbacks.onConnected) callbacks.onConnected(data);
             break;
           case 'message_added':
             if (callbacks.onMessageAdded) callbacks.onMessageAdded(data.message);
             break;
           case 'generation_started':
             if (callbacks.onGenerationStarted) callbacks.onGenerationStarted();
             break;
           case 'generation_progress':
             if (callbacks.onToken) callbacks.onToken(data.token);
             break;
           case 'generation_complete':
             if (callbacks.onGenerationComplete) callbacks.onGenerationComplete(data.message);
             break;
           case 'tool_pending':
             if (callbacks.onToolPending) callbacks.onToolPending(data);
             break;
           case 'tool_executing':
             if (callbacks.onToolExecuting) callbacks.onToolExecuting(data);
             break;
           case 'tool_output':
             if (callbacks.onToolOutput) callbacks.onToolOutput(data.output);
             break;
           case 'interrupted':
             if (callbacks.onInterrupted) callbacks.onInterrupted();
             break;
           case 'error':
             if (callbacks.onError) callbacks.onError(data.error);
             break;
         }
       };

       this.eventSource.onerror = (error) => {
         if (callbacks.onError) callbacks.onError('Event stream error');
       };
     }

     disconnect() {
       if (this.eventSource) {
         this.eventSource.close();
         this.eventSource = null;
       }
     }
   }
