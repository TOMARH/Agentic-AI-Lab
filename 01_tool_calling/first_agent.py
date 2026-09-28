def get_architecture_principle(topic: str) -> str:
    principles = {
        "microservices": "Prefer independently deployable services with clear business boundaries.",
        "api": "Design APIs around stable contracts and explicit ownership.",
        "messaging": "Assume messages can be duplicated and design consumers to be idempotent.",
    }

    return principles.get(
        topic.lower(),
        "No specific principle found for this topic."
    )

if __name__ == "__main__":
    print(get_architecture_principle("messaging"))