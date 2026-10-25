#!/usr/bin/env python3
"""
Генератор парольних фраз.

Правила:
  * 3 англійські слова, кожне з великої літери;
  * до кожного слова: 2-3 цифри та 1-2 спецсимволи;
  * порядок блоків (слово / цифри / символи) у кожній частині випадковий;
  * частини розділені нижнім підкресленням;
  * загальна довжина не більше --max-len (за замовчуванням 26);
  * слова в одній фразі не повторюються.

Використовує модуль secrets (криптографічно стійкий генератор) і вбудований
словник, тож працює без інтернету та сторонніх бібліотек (Python 3.6+).

Приклади:
  python3 passgen.py            # 10 фраз
  python3 passgen.py -n 5       # 5 фраз
  python3 passgen.py --max-len 24
"""
import argparse
import math
import secrets
from collections import defaultdict

SYMBOLS = "!@#$&?"
DIGITS = "0123456789"
WORDS_COUNT = 1
SEPARATOR = "_"
DIGITS_RANGE = (2, 3)
SYMBOLS_RANGE = (1, 2)

WORDS = """
abandon abbey ability able aboard about above abroad absence absent absorb absurd abuse
abusive academy accent accept access accord account accused ace achieve acid acquire
acre across act acting action active actor actress actual acute adapt add added address
adjust admiral admire admit adopt adopted adult advance adverse advice advise advised
adviser aerial affair affect afford afraid after again against age aged agency agenda
agent aging ago agree ahead aid aim air alarm albeit album alcohol alert algebra alien
alike alive all alley allied allow almost alone along alpha already also altar alter
always amateur amazing amber amid among amongst amount anatomy anchor ancient and
android angel anger angle angry animal anime ankle annual another answer ant antenna
anthem antique anxiety anxious any anybody anyone anyway anyways apart apology appeal
appear apple apply approve arc arch archive arctic are area arena argue arise arm armed
armor arms army around arrange array arrest arrival arrive arrow arsenal article artist
ash ashamed ashes aside ask asleep aspect assault assess asset assets assist assume
assumed assure assured asylum ate athlete atomic attack attempt attend attract auction
audio audit aunt author autism auto autumn avenue average avoid awake award aware away
awe awesome awful awhile awkward axe aye babe baby back backed backing backup bacon bad
badge badly bag bail bailey bait bake baked baker baking balance balcony bald ball
ballet balloon ballot banana band bang bangkok bank banker banking banner bar barber
barely bargain bark barn baron barrel barrier base based bash basic basin basis basket
bass batch batman bats battery batting battle bay beach beam bean bear beard bearing
beast beat beaten beating beauty because become bed bedroom beef been beer before beg
begin begun behalf behave behind being belief believe bell belle belly belong beloved
below belt bench bend beneath benefit bent berlin berry beside besides best bet better
between beyond bias bicycle bid bidding big bigger biggest bike billion bin binary
binding biology bird birth bishop bit bite biting bitter bizarre black blade blame blank
blanket blast blend bless blessed blind bliss block blocked blonde blood bloody bloom
blow blowing blown blue blues blunt board boat bodily body boil bold bolt bomb bomber
bond bone bonus boo book booked boom boost boot booth boots border bore boring born
borough borrow boss bot both bother bottle bottom bought bounce bound bout bow bowl
bowling boxing boy boycott bracket brain brake branch brand brass brave breach bread
break breast breath breathe bred breed breeze brick bridge brief briefly brigade bright
bring broad broadly broke broken broker bronze brother brown browser brush brutal bubble
buck bucket budget buffalo buffer bug build builder built bulk bull bullet bully bump
bunch bundle bunny burden bureau burial buried burke burn burned burning burnt burst
burton bury bus bush bust busy but butt butter button buttons buy buyer buzz bye cab
cabin cabinet cable cage cake calcium call calling calm camera camp campus can cancel
cancer candle candy cannon cannot canon cant canvas canyon cap capable capital captain
capture car carbon card cardiac care career careful cargo carpet carrier cart cartoon
cash casino cast casting castle casual catch cattle caught cause caution cavalry cave
cease ceiling cell cement census cent center central century certain chad chain chair
chamber champ chance change channel chaos chapel chapman chapter charge charity charm
chart charter chase chasing chat cheap cheat check checked cheek cheer cheese chef
cherry chess chest chick chicken chief child chill china chips choice choir choose
chorus chose chosen chrome chronic church cinema circle circuit circus citizen city
civic civil claim clan clarify clarity clash class classic clause clean cleaner clear
clearly clerk clever click client climate climb clinic clip clock close closed closely
closer closet closure cloth clothes cloud clown club clue cluster clutch coach coal
coast coastal coat coconut cod code coffee coffin coin coke cold collar collect college
colonel colony color colored colors column combat combine come comedy comes comfort
comic coming command comment commit common commons compact company compare compete
complex comply concept concern concert conduct cone confess confirm connect consent
consist console consult consume contact contain content contest context control convert
convey cook cooking cool cooler cooling cop cope copied copper copy coral cord core corn
corner corps correct corrupt cosmic cost costly costume cottage cotton couch cough could
council counsel count counter country county coup couple coupled coupon courage course
court cousin cover covered cow cowboy crack cracked craft crane crash crazy cream create
creator credit creep creepy crew cricket cried crime crisis critic crop cross crow crowd
crowded crown crucial crude cruel cruise crush crushed cry crying crystal cube cuisine
cult culture cup curb cure curious current curry curse curtain curve curved custody
custom customs cut cute cutting cycle cycling dad daddy daily dairy daisy dam damage
damages dame dance dancer dancing danger dare dark darling dash data date day dead
deadly deaf deal dealer dealing dear death debate debris debt debut decade decay decent
decide decided deck declare decline decree deep deeply deer default defeat defence
defend defense deficit define degree delay delete delight deliver demand den denial
dense density dental dentist deny depend deposit depot depth deputy descent desert
deserve design desire desk despair despite dessert destiny destroy detail detect develop
device devil devoted diagram dial diamond diary did die diesel diet differ dig digging
digital dignity dining dinner dioxide dip direct dirt dirty disc discuss disease dish
disk dislike dismiss display dispute distant ditch dive diverse divide divided divine
diving divorce dock doctor dodge doe does dog doing doll dollar domain dome donate
donated done donor doom door dope dose double doubled doubt dough down dozen draft drag
dragon drain drama drank draw drawer drawing drawn dream dress dressed dried drift drill
drink drive driven driver driving drone drop drought drove drum drunk dry dual duck dude
due dug dull dumb dump duo during dust duty dye dying dynamic dynasty each eager eagle
ear early earn earning earth ease easily east easy eat eaten eating echo eclipse economy
edge edit edition editor educate effect effort egg ego eight eighth either elbow elder
elderly elect elegant element eleven elite else embassy embrace emerge emotion emperor
employ empty enable end ending endless endure enemy energy enforce engage engaged engine
enhance enjoy enough ensure enter entire entity entry envy enzyme epic episode equal
equally equity era error escape escort essay essence estate esteem eternal ethical
ethics ethnic even evening event ever every evident evil evolve exact exactly examine
example exceed except excess exclude excuse execute exempt exhaust exhibit exile exist
exit exotic expand expect expense expert explain explode exploit explore export expose
exposed express extend extent extra extract extreme eye eyed fabric face faced facial
facing fact faction factor factory faculty fade fail failing failure faint fair fairly
fairy faith fake fall fallen falling false fame family famous fancy fantasy far fare
farm farmer farming farther fascist fashion fast faster fat fatal fate father fatigue
fatty fault favor fear feast feat feature fed fee feed feeding feel feeling fell fellow
felt female fence ferry fever few fiction field fierce fifteen fifth fifty fig fight
fighter figure figured file filing fill filled filling film filter filthy final finale
finally finance find finding fine finger finish fire firing firm firmly first fiscal
fish fisher fishing fist fit fitness fitting five fix fixed fixing flag flame flash flat
flavor fled flee fleet flesh flew flight flip float flood flooded floor flour flow
flower flowing flown fluid flush fly flying foam focus fog fold folded folk follow fond
font food fool foolish foot footage force forced forcing foreign forest forever forge
forget forgive forgot fork form formal format formed former forming formula fort forth
fortune forty forum forward fossil fought foul found founder four fourth fox fragile
frame framed frankly fraud freak free freedom freely freeman freeze freight fresh fried
friend fringe frog from front frost frozen fruit fry fuel fulfill full fuller fully fun
fund funded funeral funny furious further fury fusion future gain galaxy gallery gamble
game gaming gang gap garage garbage garden garlic gas gate gateway gather gauge gave
gear gem gender general generic genesis genetic genius genre gentle gently genuine
gesture get getting ghost giant gift gifted gig ginger girl give given giving glad
glance glass glasses glimpse global globe glory glow glue goal goat goddess going golden
golf gone good goods goose gospel gossip got gotten grab grade grain grammar grand
grandma grandpa granite graph graphic grasp grass grave gravity gray great greatly green
grew grey grid grief grill grind grip grocery gross ground group grove grow growing
grown growth guard guess guest guide guild guilt guilty guitar gun guru gut habit
habitat hack had hail hair hairy half halfway hall halt ham hammer hand handed handful
handle handled handy hanging happen happily happy harbor hard harder hardly hardy harm
harmful harmony harsh harvest hat hatch hate hatred haul haunted have haven hawk hay
hazard head headed header heading heal healing health healthy hear hearing heart heat
heating heaven heavily heavy heck heel height heir helmet help helpful helping hence her
herald here hero heroic hers herself hey hid hidden hide high higher highly highway hike
hill him himself hint hip hire hired his history hit hobby hockey hold holder holding
hole holiday hollow holy home honest honesty honey honor hood hook hooked hop hope
hopeful horizon hormone horn horror horse host hostage hostile hosting hot hotel hour
house housing how however hub hug huge hull human humble humor hundred hung hunger
hungry hunt hunting hurry hurt hurting husband hut hybrid hygiene ice icon idea ideal
idol ignore ill illegal illness image imagery imagine immense immune impact imply import
impose impress improve inch include income indeed index indoor induced infant inform
initial injured injury ink inland inn inner inning inquiry insane insert inside insight
insist inspire install instant instead insult intact intake intend intense intent inter
interim into invalid invest invite involve ion iron irony island isle issue item its
itself ivory ivy jacket jade jail jar jaw jazz jealous jerk jet jewelry join joint
jointly joke journal journey joy juice jump jungle junior junk jury just justice justify
karma keen keep keeper keeping kept key kick kicking kid kidney kind kindle kindly
kingdom kiss kitchen knee knew knife knight knock know knowing known lab label labor
labour lace lack lad ladder lady laid lake lamb lame lamp land landed landing lane lap
large largely laser last lasting late lately later latter laugh launch laundry law lawn
lawsuit lawyer lay layer laying lazy leader leading leaf league leak lean leaning leap
learn learned lease least leather leave leaves lecture led left leg legacy legal legally
legend legion leisure lemon lend length lengthy lens less lesser lesson let lethal
letter level levy liable liar liberal liberty library license lid lie lied life lift
lifting light lighter lightly like likely liking lily lime limit limited line linear
lined lining link linked links lion lip liquid liquor listed listen listing lit little
live lived lively liver living load loaded loading loan lobby local locally locate lock
locker lodge log logic logical lone lonely long longer look looking loop loose lose
loser losing loss lost lottery loud loudly lounge love lovely lover loving low lower
loyal loyalty luck luckily lucky luggage lunch lung luxury lying lynch machine mad
madame made madness magic magical maid maiden mail main mainly majesty make maker making
mall man manage manager mandate mankind manner manor mansion manual many map maple
marble margin marine marked marker market marking married marry marshal martial marvel
mask massage massive master match mate math matrix matter mature maximum maybe mayor
meal mean meaning meant measure meat medal medical medium meet meeting melody melt
melting member memory men mental mention mentor menu mercy mere merely merger merit
merry mess message met metal meter method metric mice mid middle midst might mighty mild
mile militia milk mill miller million mind minded mine mineral minimal minimum mining
minor mint minus minute miracle mirror misery miss missile missing mission mistake mix
mixed mixture mob mobile mock mode model modest modify module moment money monitor monk
monkey monster month monthly mood moon moral more morning mortal mosque moss most mostly
mother motion motive motor mount mounted mouse mouth move movie moving much mud mum
murphy muscle museum music musical must mutual myself mystery myth nail name namely nap
narrow nash nasty nation native natural nature naughty naval navy near nearby nearly
neat neck need needle needs neglect neither nephew nerve nervous nest network neutral
never new newly news newton next nicely niche nickel niece night nine ninth noble nobody
node noise nominee none noon nope nor normal north nose not notable notably notch note
noted nothing notice notion nova novel now nowhere nuclear number nurse nursery nursing
nut oak oath obesity obey object obscure observe obtain obvious occupy occur ocean odd
off offense offer office officer offset often oil omega once one ongoing onion only onto
open opener opening openly opera operate opinion oppose opposed optical optimal option
oral orange orbit order ordered ore organ organic origin other ought ounce our ours out
outcome outdoor outer outfit outlet outline outlook output outrage outside oval oven
over overall overly owe owl own owner oxygen pacific pack package pad pain painful paint
painted painter pair paired pal palace pale palm palmer panel panic pants papa paper par
para parade pardon parent parish park parker parking parody parole partial partly
partner party pass passage passing passion passive past paste pastor patch patent path
patient patrol pattern pause pay paying payment peace peak peanut pearl peel peer pen
penalty pencil pending penguin pension people pepper percent perfect perform perhaps
period permit person pet petty phantom phase phone photo phrase physics piano pic pick
picked pickup picnic picture pie piece pier pig pile pill pillow pin pine pink pioneer
pipe pirate piss pistol pit pitch pitcher pity place plague plain plan plane planet
plant plasma plate play player plaza plea please pledge plenty plot plug plus pocket
poem poet poetry point pointed poison poker polar police policy polite polling pond pony
pool poor poorly pope popular porch pork port portal porter portion pose possess post
postal poster posting pot potato potter pound pour poverty powder power praise pray
prayer praying precise predict prefer premier premise premium prepare present press
pretend pretty prevent prey priced pride priest primary prime prince print printer prior
prison privacy private prize pro probe problem proceed process produce product profile
profit program project promise promote prompt prone proof proper prophet propose protect
protein protest prove proven provide psychic pub public publish pull pulse pump pumpkin
punch punish punk pupil puppet puppy pure purely purple purpose purse pursue pursuit
push pushing put puzzle python qualify quality quantum quarter queen quest queue quick
quickly quiet quietly quit quite quiz quote rabbit race racial racing rack radar radical
radius rage raid rail railway rain rainbow raise raised raising rally ramp ranch random
range ranger rank rap rapid rapidly rapper rare rarely rat rate rather ratio raven raw
reach react reactor read reader readily reading ready reality realize really realm rear
reason rebel rebuild recall receipt receive recent recipe record recover recruit reduce
reed reef refer referee refined reflect reform refuge refugee refund refusal refuse
regard regime region regret regular reign reject relate related relax relay release
relief rely remain remake remedy remind remix remote removal remove removed render
renewal rent rental rep repair repeal repeat replace reply report request require rescue
reserve reset resign resist resolve resort respect respond rest resting restore result
resume retail retain retire retired retreat return reunion reveal revenge revenue
reverse review revival reward rhythm ribbon rice rid ride rider ridge riding rifle rig
right rim ring riot rip rise risen rising risk risky ritual rival rivalry river road
roast robbery robust rock rocket rocky rode role roll roller rolling roof room rooted
rope rose roster rotten rough roughly round rounded route routine row royal royalty rub
rubber rubbish ruby rude ruin rule ruler ruling run runner running runway rural rush
rushed sack sacred sad sadly sadness safe safely safety saga sage said sail sailing
sailor saint sake salad salary sale salon salt same sample sand sanders sang sat satisfy
sauce sausage savage save saving saw say saying scale scan scandal scare scary scene
scent scheme scholar science scope score scout scratch scream screen screw script scroll
sea seal search season seat second secret section sector secular secure see seed seeing
seek seem seen segment seize select self selfish sell seller senate senator send senior
sense sensor sent sequel serial series serious servant serve server service serving
session set setting settle seven seventh seventy several severe shade shaft shah shake
shall shallow shame share shark sharp sharply shave she shed sheep sheer sheet shelf
shelter sheriff shield shift shine shining shiny ship shirt shock shoe shook shoot
shooter shop shore short shortly shot shotgun should shout show shower showing shown
shrimp shut shuttle shy sick side sided siege sigh sight sign signal silence silent
silicon silk silly silver similar simple simpler simply since sincere sing singer
singing single singles sink sinking sister sit site sitting six sixteen sixth sixty size
sized sketch ski skin skinny skirt skull sky slam slap slate slavery sleep sleeve slept
slice slide sliding slight slim slip slope slot slow slowly small smart smash smell
smile smith smoke smoking smooth snack snake snap sneak soap sober social society soda
sodium sofa soft soil solar sold soldier sole solely solid solo solve some somehow song
soon sooner sore sorry sort sought soul sound soup sour source spa span spare spark
speak speaker special species specify speech speed spell spend spent sperm sphere spice
spicy spider spill spin spinal spine spiral spirit spit spite splash split spoil spoke
spoken sponsor spoon sport spot spotted spouse spray spread sprint squad square squeeze
stab stable stack stadium staff stage stake stall stamp stance stand stare stark start
starter stated static station statue status statute stay stayed steady steak steal steam
steel steep stem step stepped stick sticky stiff still sting stir stock stole stolen
stomach stood stop stopped storage store storm story strain strange strap straw streak
stream street stress stretch strict strike striker string strip stroke strong struck
stuck student studied studio study stuff stunt stupid style sub subject submit subtle
suburb subway succeed success such suck sucking sudden suffer sugar suggest suit suite
sum summary summer summit sun sunny sunrise sunset super superb supply support suppose
supreme sure surely surf surface surge surgeon surgery surplus survey survive suspect
sustain swallow swamp swan swap swear sweat sweater sweep sweet swept swift swim swing
switch sword sworn symbol system table tablet tackle tactics tag tail take taken taking
tale talent tales talk talking tall tan tank tap target task taste tasty tattoo taught
tax taxi tea teach teacher team tear tee teen teenage teens teeth tell telling temper
temple ten tenant tend tender tennis tense tension tent tenth tenure term terrace terror
test testify testing text texture than thank that theater thee theft their them theme
then theory therapy there thereby thermal these thesis they thick thief thin thing third
thirty this thou though thought thread threat three threw throat throne through throw
thrown thrust thumb thunder thus thy tick ticket tide tie tier tiger tight till timber
time timely tin tiny tip tire tired tissue title titled toast tobacco toddler toe toilet
token told toll tomato tomb ton tone tongue tonight too took tool tooth top topic torn
tornado torture toss total totally touch tough tour tourist toward towards towel tower
town toxic toy trace track tractor trade trading traffic tragedy tragic trail trailer
train trainer transit trap trash travel treason treat treaty tree trek trend trial
tribal tribe tribute trick tricky tried trigger trilogy trim trip triple trophy trouble
trout truck true truly trump trunk trust truth try tub tube tucker tuition tumor tune
tunnel turn turner turning turtle twelve twenty twice twin twist twisted twitter two
type typical ugh ugly ultra unable unaware uncle unclear under undergo unfair unhappy
uniform union unique unit unite united unity unknown unless unlike unlock until unto
unusual update upon upper upset upside uranium urge urgent urine usage use useful
useless user usual utility utter utterly vacant vaccine vacuum vague valid valley value
valued valve vampire vanilla variant varied variety various vary vast vault vector
vehicle vendor vent venture venue verbal verdict verify verse version versus very vessel
veteran via viable vicious victim victory view villa village villain vintage vinyl
violent violet virgin virtual virtue virus visa visible vision visit visitor visual
vital vitamin vocal vodka voice void voltage volume voter voting voyage wage wages wagon
waist wait waiting wake waking walk walker walking wall wallet wang want wanting war
ward warfare warm warming warmth warn warner warning warrant warrior was wash washed
washing waste wasting watch water wax way weak wealth weapon wear wearing weather web
wedding wee weed week weekly weigh weight weird welcome welfare well went were west
western wet whale what wheat wheel when where whereas wherein whether which while whilst
whip whiskey whistle white whites who whoa whoever whole wholly whom whose why wicked
wide widely widow width wife wild willing window wine wing winner winning winter wipe
wire wisdom wise wish wishing wit witch with within without witness wizard woke woman
won wonder wont woo wood wooden wool word wore work worker working world worn worry
worse worship worst worth worthy would wound wrap wreck wright wrist write writer
writing written wrong wrote yacht yang yard yea year yearly yell yelling yellow yes yet
yield yoga you young younger your yours youth zero zip zone
""".split()

BY_LEN = defaultdict(list)
for _w in sorted(set(WORDS)):
    BY_LEN[len(_w)].append(_w)

SEGMENT_TYPES = [
    (L, nd, ns)
    for L in sorted(BY_LEN)
    for nd in range(DIGITS_RANGE[0], DIGITS_RANGE[1] + 1)
    for ns in range(SYMBOLS_RANGE[0], SYMBOLS_RANGE[1] + 1)
]


def type_weight(t):
    L, nd, ns = t
    return len(BY_LEN[L]) * len(DIGITS) ** nd * len(SYMBOLS) ** ns * 6


TOTAL_WEIGHT = sum(type_weight(t) for t in SEGMENT_TYPES)


def shuffle(items):
    for i in range(len(items) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        items[i], items[j] = items[j], items[i]


def _seglen_weights():
    by_seglen = defaultdict(int)
    for t in SEGMENT_TYPES:
        by_seglen[sum(t)] += type_weight(t)
    return by_seglen


def _ways(budget, k, by_seglen, memo):
    """Кількість способів заповнити k частин, не перевищуючи budget символів."""
    if k == 0:
        return 1
    key = (budget, k)
    if key not in memo:
        memo[key] = sum(w * _ways(budget - sl, k - 1, by_seglen, memo)
                        for sl, w in by_seglen.items() if sl <= budget)
    return memo[key]


def _weighted_choice(options):
    """options: список (значення, вага)."""
    r = secrets.randbelow(sum(w for _, w in options))
    for v, w in options:
        r -= w
        if r < 0:
            return v


def make_segment(seg_len):
    types = [(t, type_weight(t)) for t in SEGMENT_TYPES if sum(t) == seg_len]
    L, nd, ns = _weighted_choice(types)
    word = secrets.choice(BY_LEN[L])
    parts = [
        word.capitalize(),
        "".join(secrets.choice(DIGITS) for _ in range(nd)),
        "".join(secrets.choice(SYMBOLS) for _ in range(ns)),
    ]
    shuffle(parts)
    # скільки різних частин має точно такий самий шаблон
    # (та сама довжина слова, к-сть цифр і символів, той самий порядок)
    pattern_count = len(BY_LEN[L]) * len(DIGITS) ** nd * len(SYMBOLS) ** ns
    return word, "".join(parts), pattern_count


def make_passphrase(max_len):
    """Рівномірний вибір серед усіх фраз, що вкладаються в max_len."""
    by_seglen = _seglen_weights()
    memo = {}
    while True:
        budget = max_len - len(SEPARATOR) * (WORDS_COUNT - 1)
        segs = []
        for k in range(WORDS_COUNT, 0, -1):
            opts = [(sl, w * _ways(budget - sl, k - 1, by_seglen, memo))
                    for sl, w in by_seglen.items() if sl <= budget]
            sl = _weighted_choice([o for o in opts if o[1] > 0])
            segs.append(make_segment(sl))
            budget -= sl
        words = [w for w, _, _ in segs]
        if len(set(words)) == WORDS_COUNT:  # без повторів слів
            phrase = SEPARATOR.join(s for _, s, _ in segs)
            bits = sum(math.log2(c) for _, _, c in segs)
            return phrase, bits


def entropy_bits(max_len):
    """Приблизна стійкість (біт) за умови, що зловмисник знає правила."""
    budget = max_len - len(SEPARATOR) * (WORDS_COUNT - 1)
    total = _ways(budget, WORDS_COUNT, _seglen_weights(), {})
    return math.log2(total) if total else 0.0


def main():
    ap = argparse.ArgumentParser(description="Генератор парольних фраз")
    ap.add_argument("-n", "--count", type=int, default=10, help="кількість фраз (10)")
    ap.add_argument("--max-len", type=int, default=26, help="макс. довжина (26)")
    args = ap.parse_args()

    min_len = WORDS_COUNT * (min(BY_LEN) + DIGITS_RANGE[0] + SYMBOLS_RANGE[0]) + WORDS_COUNT - 1
    if args.max_len < min_len:
        ap.error(f"--max-len має бути не менше {min_len}")

    width = args.max_len + 2
    print(f"{'Парольна фраза':<{width}} {'Довж.':>5}  {'Біт':>5}")
    print("-" * (width + 13))
    for _ in range(args.count):
        phrase, bits = make_passphrase(args.max_len)
        print(f"{phrase:<{width}} {len(phrase):>5}  {bits:>5.1f}")
    print("-" * (width + 13))
    print(f"Біт = стійкість, навіть якщо зловмисник знає точний шаблон фрази.")
    print(f"Стійкість генератора загалом (знає лише правила): "
          f"~{entropy_bits(args.max_len):.1f} біт. Словник: {len(set(WORDS))} слів.")


if __name__ == "__main__":
    main()
