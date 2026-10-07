# Variante ponderada

La variante oficial con valores negativos está pendiente. No se incluye un grafo
ficticio en su lugar. Importa un JSON desde la interfaz o guárdalo aquí como
`negative.json` para que se cargue al iniciar.

El JSON debe contener:

- `directed`: `true` para arcos con flechas; `false` para aristas no dirigidas.
- `nodes`: una lista de objetos con `id` entero y coordenadas finitas `x`, `y`.
- `edges`: una lista de triples `[origen, destino, peso]`. Los extremos deben
  existir en `nodes`; el peso debe ser un número finito, positivo, cero o negativo.

Los nodos no se repiten. Las aristas paralelas sí están permitidas. Para conservar
el grafo original, utiliza sus posiciones y etiquetas, incluido **666**, y cambia
únicamente los pesos que indique la nueva imagen. Indica explícitamente si también
cambian las direcciones.

Dijkstra y A* rechazan pesos negativos. Bellman–Ford calcula distancias y detecta
ciclos negativos alcanzables; los nodos afectados quedan con costo `−∞`. Un ciclo
negativo que no puede llegar al destino no invalida una ruta finita a ese destino.
En un grafo no dirigido, recorrer una arista negativa y volver por ella forma un
ciclo de costo negativo.

BFS y DFS siguen siendo recorridos; el voraz local no garantiza el mínimo. Fuerza
bruta compara **caminos simples**: con ciclos negativos, eso no representa el
problema de costo mínimo permitiendo recorridos repetidos. Su límite de pasos
sigue produciendo resultados provisionales.
