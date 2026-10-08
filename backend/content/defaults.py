"""Initial editorial copy for newly created site settings; never resets existing edits."""
def about_body():
    return [
        'Un projet commence par une ambition, une difficulté à résoudre ou une nouvelle manière de travailler. Notre rôle est de la traduire en une solution utile et adaptée à votre activité.',
        'Informatique, conseil, digitalisation, intelligence artificielle, formation et énergie : nos six domaines d’intervention permettent un accompagnement cohérent, de la réflexion à la mise en œuvre.',
    ]

def about_values():
    return [
        {'title': 'La justesse', 'description': 'Choisir des solutions qui répondent à vos besoins réels.'},
        {'title': 'La clarté', 'description': 'Rendre les choix techniques compréhensibles et les prochaines étapes concrètes.'},
        {'title': 'L’accompagnement', 'description': 'Vous donner les moyens de vous approprier les solutions et de les faire évoluer.'},
    ]

def method_steps():
    return [
        {'title': 'Échange', 'description': 'Nous analysons vos besoins et vos enjeux.'},
        {'title': 'Conception', 'description': 'Nous élaborons une solution sur mesure.'},
        {'title': 'Accompagnement', 'description': 'Nous vous guidons dans la mise en œuvre et la montée en compétence.'},
    ]
