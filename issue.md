title:	Tree-based LogManager
state:	OPEN
author:	ErikBjare
labels:	enhancement
comments:	1
assignees:	
projects:	
milestone:	
number:	17
--
I asked ChatGPT about it, and it seems doable: https://chat.openai.com/share/5b63c61e-0b82-43ee-b305-d283deba51fb

Would enable the user to stop worrying about "losing" conversation history, and let them browse the branching nature of the convo like in the ChatGPT UI.

Some complications around:

 - editing
   - after editing the conversation, read the messages and find the common ancestor and branch from there
 - saving/loading
   - a solution could be to store each branch as a log in the conversation folder side-by-side with the "main" `conversation.jsonl` branch.
