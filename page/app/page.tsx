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
  const [graphImage, setGraphImage] = useState<string>("")
  const [portfolioData, setPortfolioData] = useState<any>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [showVisualization, setShowVisualization] = useState(false)
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
      setInput("");
      setShowVisualization(false);
      setGraphImage("");
      setPortfolioData(null);

      let accumulated = "";
      const onToken = (token: string) => {
        accumulated += token;
        setMessages((prev) => {
          const newMessages = [...prev];
          // Try to parse as JSON in case it's a portfolio response
          try {
            if (accumulated.includes("Got all parameters") && accumulated.includes("getting tools")) {
              const jsonStr = accumulated.split("\n")[1]; // Get the JSON part after the parameters line
              const portfolioData = JSON.parse(jsonStr);
              setPortfolioData(portfolioData);
              setShowVisualization(true);
              newMessages[newMessages.length - 1] = { 
                role: "assistant", 
                content: accumulated.split("\n")[0] // Only show the parameters line
              };
            } else {
              newMessages[newMessages.length - 1] = { 
                role: "assistant", 
                content: accumulated 
              };
            }
          } catch (e) {
            newMessages[newMessages.length - 1] = { 
              role: "assistant", 
              content: accumulated 
            };
          }
          return newMessages;
        });

        // Check if we've received parameters for UOF visualization
        if (accumulated.includes("Got all parameters") && accumulated.includes("getting tools")) {
          setIsProcessing(true);
          // Extract parameters and send request to process visualization
          const params = accumulated.match(/Got all parameters \((.*?)\)/)?.[1];
          if (params) {
            processVisualization(params);
          }
        }
      };

      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
      await LLMResponse(input, onToken);
    }
  }

  const processVisualization = async (params: string) => {
    try {
      setIsProcessing(true);
      // Parse the parameters string into an object
      const paramPairs = params.split(', ');
      const paramObject: any = Object.fromEntries(
        paramPairs.map(pair => {
          const [key, value] = pair.split(': ');
          return [key, value];
        })
      );

      // Check if this is a portfolio request (only address and network)
      const isPortfolioRequest = Object.keys(paramObject).length === 2 && 
                                paramObject.address && 
                                paramObject.network;

      if (isPortfolioRequest) {
        // Portfolio visualization
        const response = await fetch('http://192.168.1.130:1234/v1/portfolio/visualization', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            address: paramObject.address
          })
        });
        if (!response.ok) {
          throw new Error('Failed to generate portfolio visualization');
        }
        const data = await response.json();
        setPortfolioData(data);
        setGraphImage("");
        setShowVisualization(true);
      } else {
        // UOF visualization
        const response = await fetch('http://192.168.1.130:1234/v1/uof/visualization', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            address: paramObject.address,
            token: paramObject.token,
            network: paramObject.network,
            start_block: parseInt(paramObject.start_block),
            end_block: parseInt(paramObject.end_block)
          })
        });
        if (!response.ok) {
          throw new Error('Failed to generate visualization');
        }
        const data = await response.json();
        if (data.image) {
          setGraphImage(data.image);
          setPortfolioData(null);
          setShowVisualization(true);
        } else {
          throw new Error('No image data received');
        }
      }
    } catch (error) {
      console.error('Error processing visualization:', error);
      setShowVisualization(false);
    } finally {
      setIsProcessing(false);
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit(e as any); // Cast to any to satisfy TypeScript
    }
  }

  const LLMResponse = async (input: string, onToken: (token: string) => void): Promise<{ chartType: ChartType, result: string }> => {
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

      return { chartType, result };
    } catch (error) {
      console.error("Error streaming LLM response:", error);
      onToken(" Sorry, an error occurred while fetching LLM response.");
      return { chartType: "bar", result: "" };
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
        {(showVisualization || isProcessing) && (
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle className="text-2xl text-blue-700">
                {isProcessing ? "Processing Visualization..." : "Dynamic Visualization"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isProcessing ? (
                <div className="flex items-center justify-center h-[400px]">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-700"></div>
                </div>
              ) : portfolioData ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="border p-4 text-center">
                    <h3 className="text-lg font-bold">ETH Balance</h3>
                    <p>{portfolioData.ethBalance} ETH</p>
                  </div>
                  <div className="border p-4 text-center">
                    <h3 className="text-lg font-bold">Normal Transactions</h3>
                    <p>{portfolioData.normalTxCount}</p>
                  </div>
                  <div className="border p-4 text-center">
                    <h3 className="text-lg font-bold">ERC20 Transfers</h3>
                    <p>{portfolioData.erc20TxCount}</p>
                  </div>
                </div>
              ) : graphImage ? (
                <img src={graphImage} alt="UOF Graph" style={{ width: '100%', height: 'auto' }} />
              ) : null}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

