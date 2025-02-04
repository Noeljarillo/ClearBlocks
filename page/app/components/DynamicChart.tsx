"use client"

import { Bar, BarChart, Line, LineChart, Pie, PieChart, XAxis, YAxis, Tooltip, Cell } from "recharts"
import { Card, CardContent } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import type { ChartType } from "../types"

const barData = [
  { name: "Q1", total: 1000 },
  { name: "Q2", total: 1200 },
  { name: "Q3", total: 1500 },
  { name: "Q4", total: 1800 },
]

const lineData = [
  { name: "Jan", total: 100 },
  { name: "Feb", total: 120 },
  { name: "Mar", total: 150 },
  { name: "Apr", total: 180 },
  { name: "May", total: 220 },
  { name: "Jun", total: 250 },
]

const pieData = [
  { name: "Electronics", value: 400 },
  { name: "Clothing", value: 300 },
  { name: "Food", value: 200 },
  { name: "Books", value: 100 },
]

const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042"]

interface DynamicChartProps {
  type: ChartType
}

export default function DynamicChart({ type }: DynamicChartProps) {
  const renderChart = () => {
    switch (type) {
      case "bar":
        return (
          <ChartContainer
            config={{
              total: {
                label: "Revenue",
                color: "hsl(var(--chart-1))",
              },
            }}
            className="h-[300px]"
          >
            <BarChart data={barData}>
              <XAxis dataKey="name" />
              <YAxis />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="total" />
            </BarChart>
          </ChartContainer>
        )
      case "line":
        return (
          <ChartContainer
            config={{
              total: {
                label: "Sales",
                color: "hsl(var(--chart-2))",
              },
            }}
            className="h-[300px]"
          >
            <LineChart data={lineData}>
              <XAxis dataKey="name" />
              <YAxis />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Line type="monotone" dataKey="total" stroke="hsl(var(--chart-2))" />
            </LineChart>
          </ChartContainer>
        )
      case "pie":
        return (
          <ChartContainer 
            config={{
              value: {
                label: "Value",
                color: "hsl(var(--chart-3))",
              },
            }}
            className="h-[300px]"
          >
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ChartContainer>
        )
      default:
        return <div>No chart selected</div>
    }
  }

  return (
    <Card className="bg-white shadow-lg transition-all duration-300 ease-in-out">
      <CardContent className="p-6">{renderChart()}</CardContent>
    </Card>
  )
}

