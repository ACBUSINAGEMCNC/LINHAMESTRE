import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  LucideClipboardList,
  LucideDatabase,
  LucidePackage,
  KanbanIcon as LucideLayoutKanban,
  LucideBox,
} from "lucide-react"

export default function Home() {
  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-8 text-center">ACB Usinagem CNC Ltda.</h1>
      <p className="text-center mb-8 text-gray-600">Sistema de Controle Interno de Produção</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium">Pedidos</CardTitle>
            <LucideClipboardList className="h-5 w-5 text-gray-500" />
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500 mb-4">Gerenciamento de pedidos de produção</p>
            <Link href="/pedidos">
              <Button className="w-full">Acessar</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium">Cadastros</CardTitle>
            <LucideDatabase className="h-5 w-5 text-gray-500" />
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500 mb-4">Cadastros de itens, materiais, trabalhos e clientes</p>
            <div className="space-y-2">
              <Link href="/cadastros/itens">
                <Button variant="outline" className="w-full">
                  Cadastro de Itens
                </Button>
              </Link>
              <Link href="/cadastros/materiais">
                <Button variant="outline" className="w-full">
                  Cadastro de Materiais
                </Button>
              </Link>
              <Link href="/cadastros/trabalhos">
                <Button variant="outline" className="w-full">
                  Cadastro de Trabalhos
                </Button>
              </Link>
              <Link href="/cadastros/clientes">
                <Button variant="outline" className="w-full">
                  Cadastro de Clientes
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium">Pedidos de Materiais</CardTitle>
            <LucidePackage className="h-5 w-5 text-gray-500" />
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500 mb-4">Gerenciamento de pedidos de materiais</p>
            <Link href="/pedidos-materiais">
              <Button className="w-full">Acessar</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium">Kanban ACB</CardTitle>
            <LucideLayoutKanban className="h-5 w-5 text-gray-500" />
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500 mb-4">Visualização do fluxo de produção</p>
            <Link href="/kanban">
              <Button className="w-full">Acessar</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium">Estoque</CardTitle>
            <LucideBox className="h-5 w-5 text-gray-500" />
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500 mb-4">Controle de estoque de materiais</p>
            <Link href="/estoque">
              <Button className="w-full">Acessar</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
