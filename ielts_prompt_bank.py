"""IELTS Writing Task 2 prompt bank (2026) — for Capital Normal University graduate research."""
import random

IELTS_TOPIC_BANK = [
    # Art
    {"category": "Art", "type": "Opinion", "prompt": "Art is not as important in today's world as science. To what extent do you agree?"},
    {"category": "Art", "type": "Opinion", "prompt": "International art and literature is essential in today's world. Do you agree?"},
    {"category": "Art", "type": "Direct", "prompt": "Many people support the arts. Why is that?"},
    {"category": "Art", "type": "Discussion", "prompt": "The government should spend more money supporting the arts, while others think funding should go on health care and education. Discuss both sides and give your opinion."},
    {"category": "Art", "type": "Direct", "prompt": "Traditional arts should be preserved better. Do you agree? How can this be done?"},
    {"category": "Art", "type": "Opinion", "prompt": "Many people believe the arts should be censored. Do you agree?"},
    {"category": "Art", "type": "Positive/Negative", "prompt": "Social media is changing the way we appreciate art. Is this a positive or negative trend?"},
    {"category": "Art", "type": "Opinion", "prompt": "Some people think that art is no longer important and funding should be diverted to the development of science and technology. Do you agree or disagree?"},
    # Books & Reading
    {"category": "Books", "type": "Agree/Disagree", "prompt": "Schools and parents should encourage children to read more."},
    {"category": "Books", "type": "Advantage/Disadvantage", "prompt": "What are the advantages and disadvantages of e-books?"},
    {"category": "Books", "type": "Opinion", "prompt": "The government should stop supporting public libraries because most information is available online. Do you agree?"},
    # Business & Money
    {"category": "Business", "type": "Advantage/Disadvantage", "prompt": "It is better to work for yourself than for a company. What are the advantages and disadvantages of doing so?"},
    {"category": "Business", "type": "Positive/Negative", "prompt": "Many people are spending money rather than saving it. Is this a positive or negative trend?"},
    {"category": "Business", "type": "Problem/Solution", "prompt": "Small local businesses are being threatened by large chain stores. Why is this? What can be done about it?"},
    {"category": "Business", "type": "Discussion", "prompt": "People should be encouraged to buy only domestic products, not foreign products. Other people think we should be able to buy what we prefer. Discuss both sides and give your opinion."},
    {"category": "Business", "type": "Opinion", "prompt": "No children should learn at school without learning how to manage money. Do you agree?"},
    {"category": "Business", "type": "Problem/Solution", "prompt": "Many people go into personal debt. Why is this? What can be done about it?"},
    {"category": "Business", "type": "Problem/Solution", "prompt": "Many people spend too much money on luxury goods and special events. Why is this? Is it a positive or negative trend?"},
    {"category": "Business", "type": "Opinion", "prompt": "Having a good product is the best way to be successful in business. Do you agree?"},
    {"category": "Business", "type": "Advantage/Disadvantage", "prompt": "Many companies use open-plan office spaces. What are the advantages and disadvantages of this?"},
    # Character & People
    {"category": "Character", "type": "Problem/Solution", "prompt": "Some people work harder than others. Why is this? Can someone learn how to work hard?"},
    {"category": "Character", "type": "Opinion", "prompt": "Old people have a better understanding of life. To what extent do you agree?"},
    {"category": "Character", "type": "Problem/Solution", "prompt": "Old people are becoming less respected by society and by the younger generation. Why is this happening? What can be done about it?"},
    {"category": "Character", "type": "Discussion", "prompt": "Some people follow trends, while other people set them. Why do you think this is? Do you think it is better to set trends or follow them?"},
    {"category": "Character", "type": "Opinion", "prompt": "Some people are born to be successful. Do you agree?"},
    {"category": "Character", "type": "Direct", "prompt": "Do you think character is innate or something we can cultivate? How can we develop our character?"},
    {"category": "Character", "type": "Discussion", "prompt": "Should schools encourage individuality or conformity? Which one is most beneficial for a child's future?"},
    # Crime & Punishment
    {"category": "Crime", "type": "Discussion", "prompt": "It would be quicker if there was the same punishment for the same crimes, but some people think this is not a good policy because circumstances should be considered. Discuss both sides and give your opinion."},
    {"category": "Crime", "type": "Problem/Solution", "prompt": "Too many criminals leave prison only to reoffend. Why is this? What measures can be introduced to solve this problem?"},
    {"category": "Crime", "type": "Problem/Solution", "prompt": "Crime rates are increasing in many cities. Why is this? How can this be tackled?"},
    {"category": "Crime", "type": "Opinion", "prompt": "Some people think violent films encourage criminal behaviour. To what extent do you agree?"},
    {"category": "Crime", "type": "Discussion", "prompt": "Some teenagers commit serious crime. Some people think they should get the same punishment as adults, while others disagree. Discuss both sides and give your opinion."},
    {"category": "Crime", "type": "Positive/Negative", "prompt": "Why are crime shows so popular on TV? Do you think this is a positive or negative trend?"},
    {"category": "Crime", "type": "Direct", "prompt": "Is personal safety a government responsibility or the responsibility of the individual?"},
    # Culture & Tourism
    {"category": "Culture", "type": "Discussion", "prompt": "Nearly all cities have museums or art galleries. Some people think they are a waste of funds, others disagree. Discuss both sides and give your opinion."},
    {"category": "Culture", "type": "Positive/Negative", "prompt": "Social media has brought with it globalisation. Do you think it is a positive or negative trend?"},
    {"category": "Culture", "type": "Problem/Solution", "prompt": "Traditional lifestyles are slowly being forgotten. Do you think this is a bad thing? What can be done about it?"},
    {"category": "Culture", "type": "Problem/Solution", "prompt": "Tourism to remote areas in the world is becoming more popular. Why is this? What impact does this have on local cultures?"},
    {"category": "Culture", "type": "Opinion", "prompt": "Some people think the world will one day have only one language. To what extent do you agree? Would this be a good thing?"},
    {"category": "Culture", "type": "Direct", "prompt": "All countries around the world celebrate national holidays. What role do they play? How important are they?"},
    {"category": "Culture", "type": "Opinion", "prompt": "People should be encouraged to take holidays in their own country to boost the economy. To what extent do you agree?"},
    # Education
    {"category": "Education", "type": "Problem/Solution", "prompt": "Schools should do more to instill discipline in students. How should this be done? Do you think the parents should take some responsibility for this?"},
    {"category": "Education", "type": "Discussion", "prompt": "Some people think children should be grouped together into classes, others do not agree. Discuss both sides and give your opinion."},
    {"category": "Education", "type": "Advantage/Disadvantage", "prompt": "More and more people are choosing to educate themselves online. What are the advantages and disadvantages of this?"},
    {"category": "Education", "type": "Opinion", "prompt": "Some people think that traditional subjects at school are a waste of time because soft skills and experience are more important to get a good job. Do you agree?"},
    {"category": "Education", "type": "Opinion", "prompt": "Some people think the best way to get a good job is to have a university education. To what extent do you agree?"},
    {"category": "Education", "type": "Opinion", "prompt": "Schools should give children more homework to help their academic learning. Do you think this is a good idea?"},
    {"category": "Education", "type": "Discussion", "prompt": "As children grow up they spend time both at school and at home. Do you think parents or teachers influence a child most?"},
    {"category": "Education", "type": "Discussion", "prompt": "Some people think schools should teach children right from wrong, while other people think this responsibility should fall on the parents. Discuss both sides and give your opinion."},
    {"category": "Education", "type": "Opinion", "prompt": "Education should be free for everyone. To what extent do you agree?"},
    {"category": "Education", "type": "Opinion", "prompt": "Some people think that history is a useful subject to learn, while others think it is a waste of time. What do you think?"},
    {"category": "Education", "type": "Problem/Solution", "prompt": "Education in rural areas is often not as good as in cities. Why is that? What do you think can be done about it?"},
    {"category": "Education", "type": "Problem/Solution", "prompt": "Many children think school is boring which impacts their ability to focus and negatively impacts their academic performance. What causes this problem? What solutions can you suggest?"},
    {"category": "Education", "type": "Positive/Negative", "prompt": "Having a gap year between school and university is a popular choice for many students. Do you think this is a positive trend?"},
    # Environment
    {"category": "Environment", "type": "Problem/Solution", "prompt": "Many species are becoming extinct. Do you think this is a problem? What can be done about it?"},
    {"category": "Environment", "type": "Direct", "prompt": "Do you think it is the government's or the individual's responsibility to protect the environment?"},
    {"category": "Environment", "type": "Problem/Solution", "prompt": "Many people throw litter on to the streets or in green spaces. Why is this a problem? What solutions can you suggest?"},
    {"category": "Environment", "type": "Opinion", "prompt": "Many drug companies and make-up companies test their products on animals. Do you think this is right?"},
    {"category": "Environment", "type": "Problem/Solution", "prompt": "Beauty spots are often tourist attractions. What problems does this cause? What can be done about it?"},
    {"category": "Environment", "type": "Problem/Solution", "prompt": "Many people are concerned about Climate Change. What problems does it cause? What solutions are there?"},
    # Family
    {"category": "Family", "type": "Problem/Solution", "prompt": "Children have less respect for their elders than in the past. Why is this? What can be done about it?"},
    {"category": "Family", "type": "Discussion", "prompt": "Some people think grandparents have a lot to teach their grandchildren, while others think they are too out of date to connect with them. Discuss both sides and give your opinion."},
    {"category": "Family", "type": "Discussion", "prompt": "Some people think the government should take care of the elderly, while others think the family should. Discuss both sides and give your opinion."},
    {"category": "Family", "type": "Positive/Negative", "prompt": "In the modern world, fewer families are eating their meals together. Why is this? Is it a positive or negative trend?"},
    {"category": "Family", "type": "Problem/Solution", "prompt": "Many families do not spend much time communicating with each other. What are the reasons for this? What can be done about it?"},
    {"category": "Family", "type": "Positive/Negative", "prompt": "Some women choose not to have children. Why is this? Is this a positive or negative trend?"},
    {"category": "Family", "type": "Discussion", "prompt": "Some people think parents should be strict, but others think children need more freedom to make their own choices. Discuss both sides and give your opinion."},
    # Food
    {"category": "Food", "type": "Problem/Solution", "prompt": "Traditional food is becoming less popular. Do you think this is a problem? What can be done about it?"},
    {"category": "Food", "type": "Problem/Solution", "prompt": "More and more children are eating junk food. What are the reasons for this? What can be done to solve this?"},
    {"category": "Food", "type": "Positive/Negative", "prompt": "Some people eat only organic food. What is the reason for this? Do you think it is a positive or negative trend?"},
    {"category": "Food", "type": "Discussion", "prompt": "Some people think cooking should be taught in schools, while other people think children should learn this at home. Discuss both sides and give your opinion."},
    # Health & Exercise
    {"category": "Health", "type": "Opinion", "prompt": "Schools should increase the number of sports and exercise classes to help children develop into healthy adults. What is your opinion?"},
    {"category": "Health", "type": "Opinion", "prompt": "It is the school's responsibility, not the parent's responsibility, to teach children what healthy food is. To what extent do you agree?"},
    {"category": "Health", "type": "Problem/Solution", "prompt": "Too many children spend most of their free time using screens. Why is this a problem? What solutions can you suggest?"},
    {"category": "Health", "type": "Direct", "prompt": "Many schools teach team sports in schools. Why is this?"},
    {"category": "Health", "type": "Positive/Negative", "prompt": "More and more adults are starting to prioritise their mental health. Why is this? Do you think this is a positive or negative trend?"},
    {"category": "Health", "type": "Advantage/Disadvantage", "prompt": "Many people commute to work by car or public transport, but not by cycling or walking. What are the advantages and disadvantages of this?"},
    {"category": "Health", "type": "Opinion", "prompt": "The government should spend less money on trying to cure illnesses and more money on preventing them. Do you agree?"},
    {"category": "Health", "type": "Opinion", "prompt": "Health care should be free for all people. To what extent do you agree?"},
    {"category": "Health", "type": "Opinion", "prompt": "Some sports professionals earn more money than doctors or nurses. Do you think this is right?"},
    {"category": "Health", "type": "Direct", "prompt": "International sporting events are very popular. Why is this?"},
    {"category": "Health", "type": "Opinion", "prompt": "Hobbies are healthy activities all adults should have. Do you agree?"},
]


def pick_ielts_prompts(count: int = 3) -> list[dict]:
    n = min(count, len(IELTS_TOPIC_BANK))
    return random.sample(IELTS_TOPIC_BANK, n)


def format_ielts_prompts_for_coach(prompts: list[dict]) -> str:
    lines = []
    for i, p in enumerate(prompts, 1):
        lines.append(
            f"{i}. **[{p['category']} · {p['type']}]** {p['prompt']}"
        )
    return "\n".join(lines)
