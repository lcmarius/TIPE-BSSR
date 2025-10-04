import pygraphviz as pgv

class Graphe:

  def __init__(self):
    self.sommets = {}

  def est_sommet(self, cle):
    return cle in self.sommets

  def sommet(self, cle):
    self.sommets[cle] = {}

  def list_sommets(self):
    return [key for key in self.sommets]

  def list_arcs(self):
    arcs = []
    for clef in self.sommets:
      for voisin in self.sommets[clef]:
        arcs.append((clef, voisin, self.sommets[clef][voisin]))
    return arcs

  def supprimer_sommet(self, cle1):
    if (not self.est_sommet(cle1)):
      raise Exception("Le sommet", cle1, "n'existe pas")

    for cle2 in self.sommets:
      if cle1 in self.sommets[cle2]:
        del self.sommets[cle2][cle1]
    del self.sommets[cle1]

  def taille(self):
    return len(self.sommets)

  def est_arc(self, cle1, cle2):
    return self.est_sommet(cle1) and cle2 in self.sommets[cle1]

  def set_arc(self, cle1, cle2, ponderation):
    if not self.est_sommet(cle1):
      raise Exception("Le sommet", cle2, "n'existe pas")

    if not self.est_sommet(cle2):
      raise Exception("Le sommet", cle2, "n'existe pas")

    arcs = self.sommets[cle1]
    arcs[cle2] = ponderation

  def get_arc(self, cle1, cle2):
    if not self.est_arc(cle1, cle2):
      raise Exception("L'arc entre", cle1, "-", cle2, "n'existe pas")

    return self.sommets[cle1][cle2]

  def supprimer_arc(self, cle1, cle2):
    if not self.est_arc(cle1, cle2):
      raise Exception("L'arc entre", cle1, "-", cle2, "n'existe pas")

    del self.sommets[cle1][cle2]

  def get_voisins(self, cle):
    if not self.est_sommet(cle):
      raise Exception("Le sommet", cle, "n'existe pas")
    return [key for key in self.sommets[cle]]





def graphToView(graphe, file):
  if not isinstance(graphe, Graphe):
    raise Exception("Cet objet n'est pas un graphe.")

  G = pgv.AGraph(strict=False, directed=True)
  for node in graphe.list_sommets():
    G.add_node(node)
  for arc in graphe.list_arcs():
    s1 = arc[0]
    s2 = arc[1]
    sV = arc[2]
    G.add_edge(s1, s2, label=str(sV))

  G.node_attr['shape'] = 'circle'
  G.write(file + ".dot")


def numberPonderationMapper(string):
  return int(string)

def viewToGraphe(file, ponderation_mapper):
  view = pgv.AGraph(file + ".dot")
  graphe = Graphe()
  for node in view.nodes():
    graphe.sommet(str(node))
  for edge in view.edges():
    graphe.set_arc(str(edge[0]), str(edge[1]),
                   ponderation_mapper(edge.attr["label"]))

  return graphe


'''
On fait des tests:
'''


def test_graph():
  gr = Graphe()

  gr.sommet("2")
  assert gr.est_sommet("2")
  gr.sommet("3")
  assert gr.est_sommet("3")

  gr.set_arc("2", "3", 4)
  assert gr.est_arc("2", "3")
  assert not gr.est_arc("3", "2")

  gr.supprimer_arc("2", "3")
  assert not gr.est_arc("2", "3")
  gr.set_arc("2", "3", 8)
  gr.supprimer_sommet("2")
  assert not gr.est_sommet("2")
  assert not gr.est_arc("2", "3")

  gr.sommet("8")
  gr.sommet("12")
  gr.sommet("22")
  gr.sommet("42")

  gr.set_arc("8", "12", 4)
  gr.set_arc("8", "22", 4)
  gr.set_arc("8", "42", 4)
  gr.set_arc("12", "22", 9)

  assert gr.get_voisins("8") == ["12", "22", "42"]
  assert gr.get_voisins("12") == ["22"]
  assert gr.get_voisins("22") == []

  a = Graphe()
  a.sommet("4")
  a.sommet("8")
  a.sommet("2")
  a.set_arc("4", "8", 2)
  a.set_arc("8", "2", 27)

  graphToView(a, 'test')
  viewToGraphe('test', numberPonderationMapper)


test_graph()

## Playground pour visualiser: https://magjac.com/graphviz-visual-editor/
