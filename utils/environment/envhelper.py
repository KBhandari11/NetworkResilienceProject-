import random 
import numpy as np
import torch
import networkx as nx
from scipy.stats import entropy
from igraph import Graph
from torch_geometric.data import Data

def gen_graph(cur_n, g_type,seed=None):
    random.seed(seed)
    if g_type == 'erdos_renyi':
        g = Graph.Erdos_Renyi(n=cur_n, p=random.uniform(0.10,0.15))
    elif g_type == 'powerlaw':
        g = nx.powerlaw_cluster_graph(n=cur_n, m=random.randint(2,4), p=random.uniform(0.01,0.05),seed = seed)
        g = Graph.from_networkx(g)
    elif g_type == 'small-world':
        g = nx.newman_watts_strogatz_graph(n=cur_n, k=random.randint(2,5), p=random.uniform(0.1,0.2),seed = seed)
        g = Graph.from_networkx(g)
    elif g_type == 'barabasi_albert':
        g = Graph.Barabasi(n=cur_n, m=random.randint(1,3))
    elif g_type == 'geometric':
        g = Graph.GSG(n=cur_n, radius=random.uniform(0.1,0.4))
    
    g.vs['name'] = range(cur_n)
    return g

    
def gen_new_graphs(graph_type,seed = None):
    random.seed(seed)
    np.random.seed(seed)
    a = np.random.choice(graph_type) if len(graph_type) != 1 else graph_type[0]
    number_nodes = random.randint(30,50)
    graph = gen_graph(number_nodes, a,seed)
    #graph =add_super_node(graph)
    active = 1
    graph.vs["active"] = active
    return graph    
  

def reset(graph):
    active = 1
    graph.vs["active"] = active
    return graph   

# Helper functions for game details.
def get_lcc(g):
    return len(max(g.connected_components(), key=len))
    '''subGraph = g.subgraph(np.arange(len(g)-1))
    return len(max(nx.connected_components(subGraph), key=len))#for supernode'''

def molloy_reed(g):
  all_degree = np.array(g.degree())
  #degs = all_degree
  nonmax_lcc = list(set(g.vs.indices).difference(set(max(g.connected_components(), key=len))))
  degs = np.delete(all_degree, np.array(nonmax_lcc, dtype=int))#for non max LCC
  #degs = np.delete(deg,-1)#for supernode
  k = degs.mean()
  k2 = np.mean(degs** 2)
  if k ==0:
    beta = 0
  else:
    beta = k2/k
  return beta

def global_feature(g): 
    M = g.ecount()
    N = g.vcount()
    degs = np.array(g.degree())
    k1 = degs.mean()
    k2 = np.mean(degs** 2)
    div = k2 - k1**2
    if k1 != 0:
        heterogeneity = div/k1
        density = (2*M)/(N*(N-1))
        resilience = k2/k1
        degs.sort()
        gini = np.sum(degs * (degs + 1))/(M*N) - (N+1)/N
        entrop = entropy(degs/M)/N
        transitivity = g.transitivity_undirected()
    else:
        heterogeneity = 0
        density = (2*M)/(N*(N-1))
        resilience = 0
        gini = 0
        entrop = 0
        transitivity = g.transitivity_undirected()
    global_properties = np.hstack((density,resilience,heterogeneity,gini,entrop,transitivity))
    #global_properties = np.hstack((density,resilience,heterogeneity))
    global_properties = torch.from_numpy(global_properties.astype(np.float32))#.to(device)
    return global_properties

def get_ci(g, l):
    ci = []
    degs = np.array(g.degree())
    for i in g.vs.indices:
        n = np.array([path[-1] for path in g.get_shortest_paths(i) if path and len(path) <= l])
        j = np.sum(degs[n] - 1)
        ci.append((g.degree(i) - 1) * j)
    return ci

def get_centrality_features(g):
    degree_centrality = np.array(g.degree()) / (g.vcount() - 1)
    #precolation_centrality = list(nx.percolation_centrality(g,attribute='active').values())
    #closeness_centrality = list(nx.closeness_centrality(g).values())
    eigen_centrality = np.array(g.eigenvector_centrality())
    clustering_coeff = np.array(g.transitivity_local_undirected())
    core_num = np.array(g.coreness())
    pagerank = np.array(g.pagerank())
    ci = get_ci(g, 3)
    #active = np.array(g.nodes.data("active"))[:,1]
    #x = np.column_stack((925egree_centrality,clustering_coeff,pagerank, core_num ))
    x = np.column_stack((degree_centrality,eigen_centrality,pagerank,clustering_coeff, core_num, ci ))
    #x = np.column_stack((degree_centrality,eigen_centrality,pagerank))
    return x

def features(g): 
    #actualGraph = g.g(np.arange(len(g)-1)) #for actual graph
    #x = get_centrality_features(actualGraph) #with supernode
    x = get_centrality_features(g)
    #x[:-1,:] =x_actual
    x_normed = (x - np.mean(x)) / np.std(x) #Standardize features
    #active_nodes =  np.where(np.array(list(g.nodes(data="active")))[:,1] == 0)[0]
    #x_normed[active_nodes,:]=np.zeros(np.shape(x_normed)[1])
    x = torch.from_numpy(x_normed.astype(np.float32))#.to(device)
    return x

def reduceddegree(g): 
    x = torch.FloatTensor(g.degree()).reshape((-1, 1)) - 1
    return x

def network_dismantle(board, init_lcc):
    """Checks if a line exists, returns "x" or "o" if so, and None otherwise."""
    all_nodes = np.array(board.vs["active"])
    active_nodes = np.where(all_nodes == 1)[0]
    largest_cc = get_lcc(board)
    cond = True if len(active_nodes) <= 2 or board.ecount() == 1  or (largest_cc/init_lcc) <= 0.1 else False
    return cond, largest_cc

def board_to_string(board):
    """Returns a string representation of the board."""
    return " ".join(str(f) for _, f in board.vs["active"])

def from_igraph(graph):
    edges = [edge.tuple for edge in graph.es]

    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()

    data = {}

    data["active"] = torch.tensor(graph.vs["active"])
    data['edge_index'] = edge_index.view(2, -1)
    data = Data.from_dict(data)

    data.x = data["active"].view(-1, 1)

    return data