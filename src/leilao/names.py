"""Nomes brasileiros para batizar os alunos gerados na simulação.

Cada aluno recebe um nome aleatório da forma "<nome> <sobrenome>", sorteado
sem repetição das 256 x 256 = 65.536 combinações possíveis. Puramente
cosmético: facilita a leitura das tabelas de resultado, já que ids como
"a_0137" não dizem nada ao leitor.
"""
from __future__ import annotations

import numpy as np

FIRST_NAMES: tuple[str, ...] = (
    "Adriana", "Adriano", "Afonso", "Alana", "Alberto", "Alexandre", "Alice", "Aline",
    "Allan", "Amanda", "Amélia", "Ana", "Anderson", "André", "Andrea", "Ângela",
    "Antônio", "Arthur", "Augusto", "Aurora", "Bárbara", "Beatriz", "Benedito", "Benício",
    "Bernardo", "Bianca", "Brenda", "Breno", "Bruna", "Bruno", "Caio", "Camila",
    "Carla", "Carlos", "Carolina", "Catarina", "Cecília", "César", "Cíntia", "Clara",
    "Cláudia", "Cláudio", "Cleber", "Clóvis", "Conceição", "Cristiane", "Cristiano", "Daniel",
    "Daniela", "Danilo", "Davi", "Débora", "Denise", "Diego", "Diogo", "Djalma",
    "Domingos", "Douglas", "Edson", "Eduarda", "Eduardo", "Elaine", "Elias", "Elisa",
    "Eliane", "Emanuel", "Emanuelle", "Emerson", "Enzo", "Érica", "Ester", "Eugênio",
    "Evandro", "Fabiana", "Fábio", "Fabrício", "Felipe", "Fernanda", "Fernando", "Flávia",
    "Flávio", "Francisca", "Francisco", "Gabriel", "Gabriela", "Geraldo", "Gilberto", "Gilmar",
    "Giovana", "Gisele", "Glória", "Guilherme", "Gustavo", "Helena", "Hélio", "Heloísa",
    "Henrique", "Hugo", "Iara", "Ian", "Igor", "Inês", "Ingrid", "Isabel",
    "Isabela", "Isadora", "Ismael", "Ítalo", "Ivan", "Ivone", "Jacira", "Jackson",
    "Jairo", "Janaína", "Jandira", "Jaqueline", "Jéssica", "Joana", "João", "Joaquim",
    "Jorge", "José", "Josefa", "Juliana", "Juliano", "Júlio", "Juraci", "Jussara",
    "Kaio", "Karina", "Kátia", "Kauã", "Keila", "Laís", "Lara", "Larissa",
    "Laura", "Leandro", "Leonardo", "Letícia", "Lívia", "Lorena", "Lourdes", "Luana",
    "Lucas", "Lúcia", "Luciana", "Luciano", "Luís", "Luísa", "Luiz", "Luzia",
    "Madalena", "Magda", "Maíra", "Manoel", "Manuela", "Marcela", "Marcelo", "Márcia",
    "Márcio", "Marcos", "Margarida", "Maria", "Mariana", "Marina", "Mário", "Marlene",
    "Marta", "Mateus", "Matheus", "Maurício", "Michele", "Miguel", "Milena", "Mirela",
    "Moacir", "Mônica", "Murilo", "Nádia", "Natália", "Nathan", "Neide", "Nelson",
    "Nilton", "Nívea", "Noêmia", "Norberto", "Odair", "Olívia", "Orlando", "Oscar",
    "Osvaldo", "Otávio", "Paola", "Patrícia", "Paula", "Paulo", "Pedro", "Pietra",
    "Priscila", "Rafael", "Rafaela", "Raimundo", "Raquel", "Regina", "Reinaldo", "Renan",
    "Renata", "Renato", "Ricardo", "Rita", "Roberta", "Roberto", "Rodrigo", "Rogério",
    "Romualdo", "Ronaldo", "Rosa", "Rosana", "Rubens", "Rute", "Sabrina", "Samara",
    "Samuel", "Sandra", "Santiago", "Sara", "Sebastião", "Sérgio", "Silvana", "Sílvio",
    "Simone", "Sofia", "Solange", "Sônia", "Sueli", "Tadeu", "Taís", "Talita",
    "Tamires", "Tatiana", "Telma", "Teresa", "Thaís", "Thiago", "Tiago", "Ubirajara",
    "Valéria", "Valter", "Vanessa", "Vera", "Verônica", "Vicente", "Victor", "Vinícius",
)

LAST_NAMES: tuple[str, ...] = (
    "Abrantes", "Abreu", "Acioli", "Aguiar", "Alencar", "Almeida", "Alves", "Amaral",
    "Amorim", "Andrade", "Anjos", "Antunes", "Aquino", "Aragão", "Araújo", "Arruda",
    "Assis", "Athayde", "Avelar", "Azevedo", "Badaró", "Bandeira", "Baptista", "Barbosa",
    "Barreto", "Barros", "Bastos", "Batista", "Beltrão", "Benevides", "Bernardes", "Bezerra",
    "Bittencourt", "Boaventura", "Bomfim", "Borges", "Braga", "Bragança", "Brandão", "Brito",
    "Bueno", "Caldas", "Caldeira", "Calmon", "Camargo", "Câmara", "Cambuí", "Caminha",
    "Campos", "Canuto", "Cardoso", "Carneiro", "Carvalho", "Castro", "Cavalcante", "Cavalcanti",
    "Chaves", "Cintra", "Coelho", "Coimbra", "Colares", "Conceição", "Cordeiro", "Cornélio",
    "Correia", "Costa", "Coutinho", "Couto", "Cruz", "Cunha", "Dantas", "Delgado",
    "Dias", "Diniz", "Domingues", "Dórea", "Drummond", "Duarte", "Dutra", "Esteves",
    "Estrela", "Faria", "Farias", "Feitosa", "Fernandes", "Ferraz", "Ferreira", "Figueiredo",
    "Fonseca", "Fontes", "Fraga", "França", "Franco", "Freire", "Freitas", "Frota",
    "Furtado", "Gadelha", "Galvão", "Garcia", "Gaspar", "Gomes", "Gonçalves", "Gonzaga",
    "Gouveia", "Guedes", "Guerra", "Guimarães", "Gusmão", "Henriques", "Holanda", "Jardim",
    "Jesus", "Junqueira", "Lacerda", "Lages", "Lago", "Landim", "Lara", "Leal",
    "Leão", "Leite", "Lemos", "Lima", "Lins", "Lira", "Lobato", "Lobo",
    "Lopes", "Loureiro", "Lousada", "Lucena", "Luz", "Macedo", "Machado", "Maciel",
    "Magalhães", "Maia", "Malta", "Marinho", "Marques", "Martins", "Mascarenhas", "Matos",
    "Medeiros", "Meireles", "Melo", "Mendes", "Mendonça", "Menezes", "Mesquita", "Miranda",
    "Monteiro", "Montenegro", "Moraes", "Moreira", "Mota", "Moura", "Muniz", "Nascimento",
    "Nery", "Neves", "Nobre", "Nogueira", "Nonato", "Novais", "Nunes", "Oliveira",
    "Ornelas", "Pacheco", "Padilha", "Paes", "Paiva", "Palmeira", "Parente", "Passos",
    "Pedrosa", "Peixoto", "Penha", "Pereira", "Pessoa", "Pimenta", "Pimentel", "Pinheiro",
    "Pinto", "Pires", "Portela", "Prado", "Queiroz", "Quental", "Quintela", "Rabelo",
    "Ramalho", "Ramos", "Rangel", "Raposo", "Rebouças", "Rego", "Reis", "Rezende",
    "Ribeiro", "Rios", "Rocha", "Rodrigues", "Romão", "Rosa", "Sá", "Sales",
    "Salgado", "Sampaio", "Sanches", "Santana", "Santiago", "Santos", "Saraiva", "Sarmento",
    "Seixas", "Serpa", "Serra", "Setúbal", "Severo", "Silva", "Silveira", "Simões",
    "Siqueira", "Soares", "Sodré", "Sousa", "Souza", "Tavares", "Teixeira", "Teles",
    "Tenório", "Tomás", "Torres", "Trindade", "Uchôa", "Valadares", "Valente", "Valverde",
    "Varela", "Vasconcelos", "Vaz", "Veiga", "Veloso", "Ventura", "Verçosa", "Viana",
    "Vidal", "Vieira", "Vilaça", "Vilela", "Vital", "Wanderley", "Xavier", "Zacarias",
)


def sample_names(count: int, rng: np.random.Generator) -> list[str]:
    """Sorteia `count` nomes distintos da forma "<nome> <sobrenome>"."""
    combinations = len(FIRST_NAMES) * len(LAST_NAMES)
    if count > combinations:
        raise ValueError(
            f"não há combinações suficientes para {count} alunos (máximo {combinations})"
        )
    picks = rng.choice(combinations, size=count, replace=False)
    return [
        f"{FIRST_NAMES[int(pick) // len(LAST_NAMES)]} {LAST_NAMES[int(pick) % len(LAST_NAMES)]}"
        for pick in picks
    ]
