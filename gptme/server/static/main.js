const markedHighlight = globalThis.markedHighlight.markedHighlight;
const Marked = globalThis.marked.Marked;
const hljs = globalThis.hljs;

const apiRoot = "/api/conversations";

const marked = new Marked(
  markedHighlight({
    langPrefix: "hljs language-",
    highlight(code, lang, info) {
      // check if info has ext, if so, use that as lang
      lang = info.split(".")[1] || lang;
      console.log(info);
      console.log(lang);
      const language = hljs.getLanguage(lang) ? lang : "plaintext";
      return hljs.highlight(code, { language }).value;
    },
  })
);

new Vue({
  el: "#app",
  data: {
    // List of conversations
    conversations: [],

    // Name/ID of the selected conversation
    selectedConversation: null,

    // List of messages in the selected conversation
    branch: "main",
    chatLog: [],

    // Options
    sortBy: "modified",
    showSystemMessages: false, // hide initial system messages

    // Inputs
    newMessage: "",

    // Status
    cmdout: "",
    error: "",
    generating: false,

    // Conversations limit
    conversationsLimit: 20,
  },
  async mounted() {
    this.getConversations();
    // if the hash is set, select that conversation
    if (window.location.hash) {
      this.selectConversation(window.location.hash.slice(1));
    }
    // remove display-none class from app
    document.getElementById("app").classList.remove("hidden");
    // remove loader animation
    document.getElementById("loader").classList.add("hidden");
  },
  computed: {
    sortedConversations: function () {
      const reverse = this.sortBy[0] === "-";
      const sortBy = reverse ? this.sortBy.slice(1) : this.sortBy;
      return this.conversations.sort(
        (a, b) => b[sortBy] - a[sortBy] * (reverse ? -1 : 1)
      );
    },
    preparedChatLog: function () {
      // Set hide flag on initial system messages
      for (const msg of this.chatLog) {
        if (msg.role !== "system") break;
        msg.hide = !this.showSystemMessages;
      }

      // Find branch points and annotate messages where branches occur,
      // so that we can show them in the UI, and let the user jump to them.
      this.chatLog.forEach((msg, i) => {
        msg.branches = [this.branch];

        // Check each branch if the fork at the current message
        for (const branch of Object.keys(this.branches)) {
          if (branch === this.branch) continue; // skip main branch

          // Check if the next message in current branch diverges from next message on other branch
          const next_msg = this.branches[this.branch][i + 1];
          const branch_msg = this.branches[branch][i + 1];

          // FIXME: there is a bug here in more complex cases
          if (
            next_msg &&
            branch_msg &&
            branch_msg.timestamp !== next_msg.timestamp
          ) {
            // We found a fork, so annotate the message
            msg.branches.push(branch);
            break;
          }
        }

        // Sort the branches by timestamp
        msg.branches.sort((a, b) => {
          const a_msg = this.branches[a][i + 1];
          const b_msg = this.branches[b][i + 1];
          if (!a_msg) return 1;
          if (!b_msg) return -1;
          const diff = new Date(a_msg.timestamp) - new Date(b_msg.timestamp);
          if (Number.isNaN(diff)) {
            console.error("diff was NaN");
          }
          return diff;
        });
      });

      // Convert markdown to HTML
      return this.chatLog.map((msg) => {
        msg.html = this.mdToHtml(msg.content);
        return msg;
      });
    },
  },
  methods: {
    async getConversations() {
      const res = await fetch(`${apiRoot}?limit=${this.conversationsLimit}`);
      this.conversations = await res.json();
    },
    async selectConversation(path, branch) {
      // set the hash to the conversation name
      window.location.hash = path;

      this.selectedConversation = path;
      const res = await fetch(`${apiRoot}/${path}`);

      // check for errors
      if (!res.ok) {
        this.error = res.statusText;
        return;
      }

      try {
        const data = await res.json();
        this.branches = data.branches;
        this.branches["main"] = data.log;
        this.branch = branch || "main";
        this.chatLog = this.branches[this.branch];
      } catch (e) {
        this.error = e.toString();
        console.log(e);
        return;
      }

      // TODO: Only scroll to bottom on conversation load and new messages
      this.$nextTick(() => {
        this.scrollToBottom();
      });
    },
    dismissError() {
      this.error = null;
    },
    async createConversation() {
      const name = prompt("Conversation name");
      if (!name) return;
      const res = await fetch(`${apiRoot}/${name}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([]),
      });
      if (!res.ok) {
        this.error = res.statusText;
        return;
      }
      await this.getConversations();
      this.selectConversation(name);
    },
    async sendMessage() {
      const payload = JSON.stringify({
        role: "user",
        content: this.newMessage,
        branch: this.branch,
      });
      const req = await fetch(`${apiRoot}/${this.selectedConversation}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: payload,
      });
      if (!req.ok) {
        this.error = req.statusText;
        return;
      }
      console.log(req);
      console.log(await req.json());
      this.newMessage = "";
      // reload conversation
      await this.selectConversation(this.selectedConversation, this.branch);
      // generate
      this.generate();
    },
    async generate() {
      this.generating = true;
      const req = await fetch(
        `${apiRoot}/${this.selectedConversation}/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ branch: this.branch }),
        }
      );
      this.generating = false;
      if (!req.ok) {
        this.error = req.statusText;
        return;
      }
      // req.json() can contain (not stored) responses to /commands,
      // or the result of the generation.
      // if it's unsaved results of a command, we need to display it
      const data = await req.json();
      if (data.length == 1 && data[0].stored === false) {
        this.cmdout = data[0].content;
      }
      // reload conversation
      await this.selectConversation(this.selectedConversation, this.branch);
    },
    changeBranch(branch) {
      this.branch = branch;
      this.chatLog = this.branches[branch];
    },
    backToConversations() {
      this.getConversations(); // refresh conversations
      this.selectedConversation = null;
      this.chatLog = [];
      window.location.hash = "";
    },
    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.chatContainer;
        container.scrollTop = container.scrollHeight;
      });
    },
    fromNow(timestamp) {
      return moment(new Date(timestamp)).fromNow();
    },
    mdToHtml(md) {
      // TODO: Use DOMPurify.sanitize
      md = this.wrapThinkingInDetails(md);
      let html = marked.parse(md);
      html = this.wrapBlockInDetails(html);
      return html;
    },

    wrapBlockInDetails(text) {
      const codeBlockRegex =
        /<pre><code class="([^"]+)">([\s\S]*?)<\/code><\/pre>/g;
      return text.replace(codeBlockRegex, function (match, classes, code) {
        const langtag = (classes.split(" ")[1] || "Code").replace(
          "language-",
          ""
        );
        return `<details><summary>${langtag}</summary><pre><code class="${classes}">${code}</code></pre></details>`;
      });
    },

    wrapThinkingInDetails(text) {
      // replaces <thinking>...</thinking> with <details><summary>Thinking</summary>...</details>
      const thinkingBlockRegex = /<thinking>([\s\S]*?)<\/thinking>/g;
      return text.replace(thinkingBlockRegex, function (match, content) {
        return `<details><summary>Thinking</summary>\n\n${content}\n\n</details>`;
      });
    },

    changeSort(sortBy) {
      // if already sorted by this field, reverse the order
      if (this.sortBy === sortBy) {
        this.sortBy = `-${sortBy}`;
      } else {
        this.sortBy = sortBy;
      }
    },
    capitalize(string) {
      return string.charAt(0).toUpperCase() + string.slice(1);
    },
    async loadMoreConversations() {
      this.conversationsLimit += 100;
      await this.getConversations();
    },
  },
});
