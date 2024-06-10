import numpy as np
import random
import json
import pickle
from pyboy import PyBoy
from pyboy.utils import WindowEvent
import time

class Ambiente:
    def __init__(self, nome_arquivo='mario.gb', modo_silencioso=True):
        tipo_janela = "headless" if modo_silencioso else "SDL2"
        self.pyboy = PyBoy(nome_arquivo, window=tipo_janela, debug=modo_silencioso)
        self.pyboy.set_emulation_speed(150)
        self.mario = self.pyboy.game_wrapper
        self.mario.start_game()
        self.botao_pulo_pressionado = False
        self.botao_abaixar_pressionado = False
        self.contador_pulo = 0

    def calcular_fitness(self):
        return self.mario.score + 2 * self.mario.level_progress + self.mario.time_left 

    def fim_de_jogo(self):
        return self.mario.lives_left == 1 or self.mario.score < 0

    def reset(self):
        self.mario.reset_game()
        self.pyboy.tick()
        return self.get_estado()

    def passo(self, indice_acao, duracao):
        if self.fim_de_jogo():
            print("Fim de jogo detectado")
            return None, 0, 0, "Fim de Jogo"
        
        acoes = {
            0: [WindowEvent.PRESS_ARROW_LEFT],
            1: [WindowEvent.PRESS_ARROW_RIGHT],
            2: [WindowEvent.PRESS_ARROW_DOWN],  # Ação de abaixar
            3: [WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.PRESS_BUTTON_A],  # Pulo curto com movimento para a direita
            4: [WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.PRESS_BUTTON_A]   # Pulo longo com movimento para a direita
        }
        acoes_liberacao = {
            0: [WindowEvent.RELEASE_ARROW_LEFT],
            1: [WindowEvent.RELEASE_ARROW_RIGHT],
            2: [WindowEvent.RELEASE_ARROW_DOWN],  # Liberação da ação de abaixar
            3: [WindowEvent.RELEASE_ARROW_RIGHT, WindowEvent.RELEASE_BUTTON_A],
            4: [WindowEvent.RELEASE_ARROW_RIGHT, WindowEvent.RELEASE_BUTTON_A]
        }

        acao = acoes.get(indice_acao, [WindowEvent.PASS])
        for evento in acao:
            self.pyboy.send_input(evento)
            if evento == WindowEvent.PRESS_BUTTON_A:
                self.botao_pulo_pressionado = True
                self.contador_pulo = 0
            elif evento == WindowEvent.PRESS_ARROW_DOWN:
                self.botao_abaixar_pressionado = True
        for _ in range(duracao):
            self.pyboy.tick()
            if self.botao_pulo_pressionado:  # Mantém o botão de pulo pressionado durante toda a duração
                self.contador_pulo += 1
                if self.contador_pulo >= 10:  # Reduza ou aumente o número conforme necessário para ajustar a duração do pulo
                    self.pyboy.send_input(WindowEvent.RELEASE_BUTTON_A)
            elif self.botao_abaixar_pressionado:
                pass  # Mantém o botão de abaixar pressionado durante toda a duração
        acao_liberacao = acoes_liberacao.get(indice_acao, [WindowEvent.PASS])
        for evento in acao_liberacao:
            self.pyboy.send_input(evento)
            if evento == WindowEvent.RELEASE_BUTTON_A:
                self.botao_pulo_pressionado = False
                self.contador_pulo = 0
            elif evento == WindowEvent.RELEASE_ARROW_DOWN:
                self.botao_abaixar_pressionado = False
        self.pyboy.tick()

        tempo_restante = self.mario.time_left
        progresso_nivel = self.mario.level_progress
        return self.get_estado(), self.calcular_fitness(), tempo_restante, progresso_nivel

    def get_estado(self):
        return np.asarray(self.mario.game_area())

    def fechar(self):
        self.pyboy.stop()

    def get_estado(self):
        return np.asarray(self.mario.game_area())

    def fechar(self):
        self.pyboy.stop()

class Individuo:
    def __init__(self):
        self.acoes = [(random.choices([0, 1, 2, 3], weights=[1.5, 2, 4, 1])[0], random.randint(1, 10)) for _ in range(5000)]

        self.fitness = 0
        self.pontos_tempo = 0
        self.movimentos_direita = 0

    def avaliar(self, ambiente):
        estado = ambiente.reset()
        fitness_total = 0
        tempo_maximo = 0
        movimentos_direita = 0
        jogo_terminou = False
        tempo_ocioso = 0  # Tempo sem fazer movimentos significativos

        for acao, duracao in self.acoes:
            if jogo_terminou == "Fim de Jogo":
                break
            novo_estado, fitness, tempo_restante, jogo_terminou = ambiente.passo(acao, duracao)
            fitness_total += fitness
            tempo_maximo = max(tempo_maximo, tempo_restante)
            movimentos_direita += 1 if acao in [1, 3] else 0  # Conta movimentos para direita, incluindo os de abaixar
            if acao not in [1, 3]:  # Se não foi um movimento para a direita ou abaixar
                tempo_ocioso += 1
            else:
                tempo_ocioso = 0  # Resetar o contador se um movimento significativo for feito
            estado = novo_estado

        pontos_tempo = 100 if tempo_maximo > 0 else 0
        penalidade_repeticao = -len([1 for i in range(len(self.acoes) - 1) if self.acoes[i] == self.acoes[i+1]]) * 10
        penalidade_tempo_ocioso = -tempo_ocioso  # Penalizar por tempo ocioso
        self.fitness = fitness_total + pontos_tempo + movimentos_direita * 5 + penalidade_repeticao + penalidade_tempo_ocioso
        return self.fitness


def avaliar_fitness(individuo, ambiente):
    fitness = individuo.avaliar(ambiente)
    fitness_normalizado = fitness / 10000
    fitness_peso_pulo = fitness_normalizado + individuo.movimentos_direita * 5  # Adicionando mais peso para os movimentos para a direita
    return fitness_peso_pulo

def iniciar_individuos(populacao):
    return [Individuo() for _ in range(populacao)]

def selecao(populacao):
    tamanho_torneio = 3
    print("Population size:", len(populacao))  # Debug print
    selecionadas = []
    while len(selecionadas) < len(populacao):
        torneio = random.sample(populacao, tamanho_torneio)
        vencedor = max(torneio, key=lambda individuo: individuo.fitness)
        selecionadas.append(vencedor)
    return selecionadas

def cruzamento(pai1, pai2):
    filho1_acoes = []
    filho2_acoes = []

    for gene_pai1, gene_pai2 in zip(pai1.acoes, pai2.acoes):
        # Escolhe aleatoriamente de qual pai será herdado o gene
        if random.random() < 0.5:
            filho1_acoes.append(gene_pai1)
            filho2_acoes.append(gene_pai2)
        else:
            filho1_acoes.append(gene_pai2)
            filho2_acoes.append(gene_pai1)

    filho1 = Individuo()
    filho1.acoes = filho1_acoes

    filho2 = Individuo()
    filho2.acoes = filho2_acoes

    return filho1, filho2

def mutacao(individuo, taxa_mutacao=0.1):
    for i in range(len(individuo.acoes)):
        if random.random() < taxa_mutacao:
            acao_mutada = random.choices([2, 1], weights=[3, 1])[0]
            duracao_mutada = random.randint(1, 10)
            individuo.acoes[i] = (acao_mutada, duracao_mutada)

def imprimir_acoes_individuo(individuo):
    nomes_acoes = ["esquerda", "direita", "direita e pulo curto", "direita e pulo longo"]
    acoes = [f"{nomes_acoes[acao]} por {duracao} ticks" for acao, duracao in individuo.acoes]
    return acoes

def algoritmo_genetico(populacao, ambiente, geracoes=100, tamanho_populacao=20):
    tamanho_inicial_populacao = tamanho_populacao
    melhor_individuo = populacao[0]  # Inicialize com o primeiro indivíduo da população
    melhor_fitness = melhor_individuo.fitness  # Inicialize com o fitness do primeiro indivíduo

    for geracao in range(geracoes):
        for individuo in populacao:
            individuo.fitness = avaliar_fitness(individuo, ambiente)
            print(f"Fitness: {individuo.fitness}")

        selecionadas = selecao(populacao)
        descendentes = []
        while len(descendentes) < tamanho_populacao - 1:  # Manter apenas o melhor indivíduo da geração anterior
            pai1, pai2 = random.sample(selecionadas, 2)
            filho1, filho2 = cruzamento(pai1, pai2)
            descendentes.extend([filho1, filho2])

        for filho in descendentes:
            mutacao(filho)

        # Mantenha o melhor indivíduo da geração anterior
        populacao = [melhor_individuo] + iniciar_individuos(tamanho_populacao - 1)

        fitness_atual = max(individuo.fitness for individuo in populacao if individuo is not None)
        individuo_atual = max(populacao, key=lambda n: n.fitness if n is not None else float('-inf'))
        if fitness_atual > melhor_fitness:
            melhor_fitness = fitness_atual
            melhor_individuo = individuo_atual

        print(f"Geração {geracao}: Melhor Fitness {melhor_fitness}")
        print(f"Melhores Ações: {imprimir_acoes_individuo(melhor_individuo)}")

        # Exibir melhor fitness ao final de cada jogo
        if ambiente.fim_de_jogo():
            print(f"Melhor fitness ao final do jogo: {melhor_individuo.fitness}")

        # Repopulação
        populacao.sort(key=lambda x: x.fitness if x is not None else float('-inf'), reverse=True)
        melhores = populacao[:tamanho_inicial_populacao // 2]
        descendentes.sort(key=lambda x: x.fitness, reverse=True)
        proxima_geracao = melhores + descendentes[:tamanho_inicial_populacao - len(melhores)]
        populacao = proxima_geracao

    return melhor_individuo




def rodar_melhor_modelo(ambiente, melhor_individuo):
    while True:
        estado = ambiente.reset()
        for acao in melhor_individuo.acoes:
            estado, fitness, tempo_restante, progresso_nivel = ambiente.passo(acao)

        print("Loop completado, reiniciando...")

ambiente = Ambiente(modo_silencioso=False)
populacao = iniciar_individuos(20)  
algoritmo_genetico(populacao, ambiente)
