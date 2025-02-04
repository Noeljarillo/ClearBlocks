import { Avatar, AvatarFallback } from "@/components/ui/avatar"

interface ChatMessageProps {
  role: string
  content: string
}

export default function ChatMessage({ role, content }: ChatMessageProps) {
  return (
    <div className={`flex gap-3 mb-4 ${role === "assistant" ? "flex-row-reverse" : ""}`}>
      <Avatar className={role === "assistant" ? "bg-blue-500" : "bg-green-500"}>
        <AvatarFallback>{role === "user" ? "U" : "AI"}</AvatarFallback>
      </Avatar>
      <div
        className={`rounded-lg p-3 max-w-[70%] ${
          role === "assistant" ? "bg-blue-100 text-blue-800" : "bg-green-100 text-green-800"
        }`}
      >
        {content}
      </div>
    </div>
  )
}

