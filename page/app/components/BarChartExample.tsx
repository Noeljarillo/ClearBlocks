"use client"

import { Bar, BarChart, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

const data = [
  { name: "Jan", total: 167 },
  { name: "Feb", total: 190 },
  { name: "Mar", total: 210 },
  { name: "Apr", total: 252 },
  { name: "May", total: 284 },
  { name: "Jun", total: 329 },
]

export default function BarChartExample() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Monthly Sales</CardTitle>
        <CardDescription>A bar chart showing monthly sales data</CardDescription>
      </CardHeader>
      <CardContent className="pb-4">
        <ChartContainer
          config={{
            total: {
              label: "Total",
              color: "hsl(var(--chart-1))",
            },
          }}
          className="h-[300px]"
        >
          <BarChart data={data}>
            <XAxis dataKey="name" />
            <YAxis />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="total" />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}

