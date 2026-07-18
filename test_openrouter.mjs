import { OpenRouter } from "@openrouter/sdk";

const openrouter = new OpenRouter({
  apiKey: "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"
});

// Stream the response to get reasoning tokens in usage
const stream = await openrouter.chat.send({
  model: "nvidia/nemotron-3-super-120b-a12b:free",
  messages: [
    {
      role: "user",
      content: "How many r's are in the word 'strawberry'?"
    }
  ],
  stream: true
});

let response = "";
for await (const chunk of stream) {
  const content = chunk.choices[0]?.delta?.content;
  if (content) {
    response += content;
    process.stdout.write(content);
  }

  // Usage information comes in the final chunk
  if (chunk.usage) {
    console.log("\nReasoning tokens:", chunk.usage.reasoningTokens);
  }
}
