"use client"

import { useState, useRef, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import ChatMessage from "./components/ChatMessage"
import DynamicChart from "./components/DynamicChart"
import type { ChartType } from "./types"

export default function Home() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([])
  const [input, setInput] = useState("")
  const [currentChart, setCurrentChart] = useState<ChartType>("bar")
  const scrollAreaRef = useRef<HTMLDivElement>(null)

  // Auto-scroll effect
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollElement = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollElement) {
        scrollElement.scrollTop = scrollElement.scrollHeight
      }
    }
  }, [messages]) // Scroll whenever messages change

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      setMessages((prev) => [...prev, { role: "user", content: input }]);
      
      // Clear the input immediately after sending the message
      setInput("");

      // Add an empty assistant message to update progressively
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      let accumulated = "";
      const onToken = (token: string) => {
        accumulated += token;
        setMessages((prev) => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1] = { role: "assistant", content: accumulated };
          return newMessages;
        });
      };

      const { chartType } = await LLMResponse(input, onToken);
      setCurrentChart(chartType);
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit(e as any); // Cast to any to satisfy TypeScript
    }
  }

  const LLMResponse = async (input: string, onToken: (token: string) => void): Promise<{ chartType: ChartType }> => {
    let result = "";
    let buffer = "";
    try {
      const response = await fetch('http://192.168.1.130:1234/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [{ role: 'user', content: input }], stream: true })
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error("No response body received from LM Studio Server");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let done = false;

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          // Keep the last, possibly incomplete, line in the buffer
          buffer = lines.pop() || "";
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            // Remove 'data:' prefix if present
            let jsonLine = trimmed.startsWith("data:") ? trimmed.replace(/^data:\s*/, "") : trimmed;
            if (jsonLine === "[DONE]") continue;
            try {
              const parsed = JSON.parse(jsonLine);
              const token = parsed?.choices?.[0]?.delta?.content;
              if (token) {
                onToken(token);
                result += token;
              }
            } catch (e) {
              console.error("Failed to parse JSON:", e, jsonLine);
            }
          }
        }
      }

      // Process any remaining content in the buffer
      const leftover = buffer.trim();
      if (leftover.startsWith("data:")) {
        let jsonLine = leftover.replace(/^data:\s*/, "");
        if (jsonLine !== "[DONE]") {
          try {
            const parsed = JSON.parse(jsonLine);
            const token = parsed?.choices?.[0]?.delta?.content;
            if (token) {
              onToken(token);
              result += token;
            }
          } catch (e) {
            console.error("Failed to parse leftover JSON:", e, jsonLine);
          }
        }
      }

      let chartType: ChartType = "bar";
      if (input.toLowerCase().includes("line") || result.toLowerCase().includes("line")) {
        chartType = "line";
      } else if (input.toLowerCase().includes("pie") || result.toLowerCase().includes("pie")) {
        chartType = "pie";
      }

      return { chartType };
    } catch (error) {
      console.error("Error streaming LLM response:", error);
      onToken(" Sorry, an error occurred while fetching LLM response.");
      return { chartType: "bar" };
    }
  }

  return (
    <div className="container mx-auto p-4 min-h-screen bg-gradient-to-b from-blue-100 to-purple-100">
      <h1 className="text-4xl font-bold mb-8 text-center text-blue-800">ClearBlocks</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle className="text-2xl text-blue-700">Interactive Chat</CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea ref={scrollAreaRef} className="h-[400px] mb-4 p-4 border rounded-lg bg-white">
              {messages.map((message, index) => (
                <ChatMessage key={index} role={message.role} content={message.content} />
              ))}
            </ScrollArea>
            <form onSubmit={handleSubmit} className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about sales, products, or request a specific chart type..."
                className="flex-grow"
              />
              <Button type="submit" className="bg-blue-600 hover:bg-blue-700">
                Send
              </Button>
            </form>
          </CardContent>
        </Card>
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle className="text-2xl text-blue-700">Dynamic Visualization</CardTitle>
          </CardHeader>
          <CardContent>
            <DynamicChart type={currentChart} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

