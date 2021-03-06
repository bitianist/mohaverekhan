import uuid
import json
import re
from collections import OrderedDict
import logging
from django.contrib.postgres.fields import JSONField, ArrayField
from django.db import models
from django import forms
# from mohaverekhan.operators.taggers.formal import model as formal_model
# from mohaverekhan.operators.taggers.informal import model as informal_model
# from mohaverekhan.operators.normalizers.seq2seq import model as seq2seq_model
from colorfield.fields import ColorField
from django.db.models import Count, Q
from nltk.metrics import accuracy

from mohaverekhan import cache
from django.utils.html import format_html

logger = None

from django.contrib.postgres.forms.jsonb import (
    InvalidJSONInput,
    JSONField as JSONFormField,
)

sentence_splitter_pattern = re.compile(r'([!\.\?⸮؟]+)[ \n]+|[ \n]+([!\.\?⸮؟]+)')
error_tag = {'name':'ERROR', 'persian':'خطا', 'color':'#FF0000'}

def split_into_token_contents(text_content, delimiters='[ \n]+'):
    return re.split(delimiters, text_content)

class UTF8JSONFormField(JSONFormField):

    def prepare_value(self, value):
        if isinstance(value, InvalidJSONInput):
            return value
        return json.dumps(value, ensure_ascii=False, indent=4,)

class UTF8JSONField(JSONField):
    """JSONField for postgres databases.

    Displays UTF-8 characters directly in the admin, i.e. äöü instead of
    unicode escape sequences.
    """

    def formfield(self, **kwargs):
        return super().formfield(**{
            **{'form_class': UTF8JSONFormField},
            **kwargs,
        })

# باید فاصله تو توکن ها رو تبدیل به نیم فاصله کنم تو ایمورت داده ها

class Word(models.Model):
    logger = logging.getLogger(__name__)
    created = models.DateTimeField(auto_now_add=True)
    content = models.CharField(max_length=200)
    normalizers = models.ManyToManyField('Normalizer', through='WordNormal', related_name='words', 
                            related_query_name='word', blank=True, through_fields=('word', 'normalizer'),)

    class Meta:
        verbose_name = 'Word'
        verbose_name_plural = 'Words'
        ordering = ('-created',)

    def __str__(self):
        return f'{self.content[:120]}{" ..." if len(self.content) > 120 else ""}'

class WordNormal(models.Model):
    logger = logging.getLogger(__name__)
    created = models.DateTimeField(auto_now_add=True)
    content = models.CharField(max_length=200)
    normalizer = models.ForeignKey('Normalizer', on_delete=models.CASCADE, related_name='word_normals', related_query_name='word_normal')
    word = models.ForeignKey('Word', on_delete=models.CASCADE, related_name='word_normals', related_query_name='word_normal')
    is_valid = models.BooleanField(default=None, blank=True, null=True)
    validator = models.ForeignKey('Validator', on_delete=models.CASCADE, related_name='word_normals', related_query_name='word_normal', blank=True, null=True)

    class Meta:
        verbose_name = 'Word Normal'
        verbose_name_plural = 'Word Normals'
        ordering = ('-created',)

    def check_validation(self):
        if self.normalizer.name == 'mohaverekhan-manual-normalizer':
            self.is_valid = True
            self.validator = cache.validators['mohaverekhan-validator']
            

    def save(self, *args, **kwargs):
        self.check_validation()        
        super(WordNormal, self).save(*args, **kwargs)
    
    def __str__(self):
        return f'{self.content[:120]}{" ..." if len(self.content) > 120 else ""}'

class Text(models.Model):
    logger = logging.getLogger(__name__)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    content = models.TextField()
    normalizers = models.ManyToManyField('Normalizer', through='TextNormal', related_name='texts', 
                            related_query_name='text', blank=True, through_fields=('text', 'normalizer'),)
    normalizers_sequence = ArrayField(models.CharField(max_length=200), blank=True, default=list)

    class Meta:
        verbose_name = 'Text'
        verbose_name_plural = 'Texts'
        ordering = ('-created',)

    def __str__(self):
        return f'{self.content[:120]}{" ..." if len(self.content) > 120 else ""}'

    @property
    def total_text_tag_count(self):
        return self.text_tags.count()
    
    @property
    def total_text_normal_count(self):
        return self.text_normals.count()

class TextNormal(Text):
    logger = logging.getLogger(__name__)
    normalizer = models.ForeignKey('Normalizer', on_delete=models.CASCADE, related_name='text_normals', related_query_name='text_normal')
    text = models.ForeignKey('Text', on_delete=models.CASCADE, related_name='text_normals', related_query_name='text_normal')
    is_valid = models.BooleanField(default=None, blank=True, null=True)
    validator = models.ForeignKey('Validator', on_delete=models.CASCADE, related_name='text_normals', related_query_name='text_normal', blank=True, null=True)
    
    class Meta:
        verbose_name = 'Text Normal'
        verbose_name_plural = 'Text Normals'
        ordering = ('-created',)

    def check_validation(self):
        if self.normalizer.name == 'mohaverekhan-manual-normalizer':
            self.is_valid = True
            self.validator = cache.validators['mohaverekhan-validator']

    def check_normalizers_sequence(self):
        if self.text.normalizers_sequence:
            if self.text.normalizers_sequence[-1] != self.normalizer.name:
                self.normalizers_sequence = self.text.normalizers_sequence \
                                                + [self.normalizer.name]
        else:
            self.normalizers_sequence = [self.normalizer.name]
            
    def save(self, *args, **kwargs):
        self.check_validation()        
        self.check_normalizers_sequence()
        super(TextNormal, self).save(*args, **kwargs)

class TextTag(models.Model):
    logger = logging.getLogger(__name__)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    tagger = models.ForeignKey('Tagger', on_delete=models.CASCADE, related_name='text_tags', related_query_name='text_tag')
    text = models.ForeignKey('Text', on_delete=models.CASCADE, related_name='text_tags', related_query_name='text_tag')
    tagged_tokens = UTF8JSONField(default=list) # contains list of token with it's tag
    accuracy = models.FloatField(default=0, blank=True)
    true_text_tag = models.ForeignKey('self', on_delete=models.CASCADE, related_name='+', blank=True, null=True)
    is_valid = models.BooleanField(default=None, blank=True, null=True)
    validator = models.ForeignKey('Validator', on_delete=models.CASCADE, related_name='text_tags', related_query_name='text_tag', 
                                        blank=True, null=True)
    # tags_string = models.TextField(blank=True, default='')
    # tagged_tokens_html = models.TextField(blank=True, default=format_html(''))
    
    class Meta:
        verbose_name = 'Text Tag'
        verbose_name_plural = 'Text Tags'
        ordering = ('-created',)

    @property
    def number_of_tagged_tokens(self):
        return len(self.tagged_tokens)
    
    @property
    def tags_string(self):
        tags_string = ''
        if self.tagged_tokens:
            for tagged_token in self.tagged_tokens:
                if tagged_token['token'] == '\\n':
                    tags_string += 'O \n '
                else:
                    tags_string += tagged_token['tag']['name'] + ' ' 
        tags_string = tags_string.strip()
        return tags_string

    @property
    def tagged_tokens_html(self):
        tagged_tokens_html = format_html('')
        if self.tagged_tokens:
            for tagged_token in self.tagged_tokens:
                if 'tag' in tagged_token:
                    if tagged_token['token'] == '\\n':
                        tagged_tokens_html += format_html(f'<br />')
                    else:
                        # html += format_html(f'<div>hello</div>')
                        tagged_tokens_html += format_html('''
<div style="color:{0};display: inline-block;">
    {1}_{2}&nbsp;&nbsp;&nbsp;
</div>
                        ''', tagged_token["tag"]["color"], tagged_token['token'], tagged_token["tag"]["name"])

        tagged_tokens_html = format_html('''
            <div style="background-color: #44444e !important;direction: rtl !important;text-align: right;padding: 0.5vh 1.0vw 0.5vh 1.0vw;">
                {}
            </div>
            ''', tagged_tokens_html)
        return tagged_tokens_html               

    def check_validation(self):
        if self.tagger is not None and self.tagger.name in ('bijankhan-manual-tagger', 
                                                'mohaverekhan-manual-tagger'):
            self.is_valid = True
            self.validator = cache.validators['mohaverekhan-validator']
            # self.accuracy = 100

    def set_tag_details(self):
        tag_details_dictionary = {tag.name:tag for tag in self.tagger.tag_set.tags.all()}
        referenced_tag, referenced_token, referenced_token_tag = None, None, None
        for tagged_token in self.tagged_tokens:
            if 'tag' in tagged_token and 'name' in tagged_token['tag']:
                if tagged_token['tag']['name'] not in tag_details_dictionary:
                    tagged_token['tag'] = error_tag
                    # self.tagger.tag_set.add_to_unknown_tag_examples(token['token'])
                    continue

                referenced_tag = tag_details_dictionary[tagged_token['tag']['name']]
                # referenced_tag.add_to_examples(tagged_token['token'])
                tagged_token['tag']['persian'] = referenced_tag.persian
                tagged_token['tag']['color'] = referenced_tag.color

                if self.is_valid:
                    referenced_token, created = Token.objects.get_or_create(content=tagged_token['token'])
                    # self.logger.info(f'> referenced_token : {referenced_token.id} {referenced_token}')
                    # self.logger.info(f'> referenced_tag : {referenced_tag.id} {referenced_tag}')
                    referenced_token_tag, created = TokenTag.objects.get_or_create(
                        token=referenced_token,
                        tag=referenced_tag
                    )
                    # referenced_token_tag.update_number_of_repetitions()


    def save(self, *args, **kwargs):
        self.check_validation()
        self.set_tag_details()
        super(TextTag, self).save(*args, **kwargs)

    def __unicode__(self):
        rep = ""
        if self.tagged_tokens:
            for tagged_token in self.tagged_tokens:
                rep += f'{tagged_token["token"]}_{tagged_token["tag"]["name"]} '
        return rep

    def __str__(self):  
        return format_html(
            '<a href="http://127.0.0.1:8000/admin/mohaverekhan/texttag/{}/change/">{}</a>', 
            self.id, 
            format_html(
                self.tags_string[0:50].replace(r'}', r'}}').replace(r'{', r'{{').replace('\n', format_html('<br />')) + format_html(" ..." if len(self.tags_string) > 50 else "")
                    )
            )

    def evaluate(self, predicted_text_tag):
        predicted_tags_string = predicted_text_tag.tags_string.replace('\n', ' ').strip().split()
        true_tags_string = self.tags_string.replace('\n', ' ').strip().split()
        asses = zip(predicted_tags_string, true_tags_string)
        newline = '\n'
        self.logger.info(f'asses : \n{newline.join([ass.__str__() for ass in asses])}\n')
        predicted_text_tag.accuracy = accuracy(true_tags_string, predicted_tags_string) * 100
        predicted_text_tag.true_text_tag = self
        predicted_text_tag.save()
        return predicted_text_tag

    
# def get_unknown_tag():
#     return {'name':'unk', 'persian':'نامشخص', 'color':'#FFFFFF', 'examples':[]}

class TagSet(models.Model):
    logger = logging.getLogger(__name__)
    created = models.DateTimeField(auto_now_add=True)
    name = models.SlugField(default='unknown-tag-set', unique=True)
    last_update = models.DateTimeField(auto_now=True)
    # unknown_tag = UTF8JSONField(blank=True, default=get_unknown_tag)

    def __str__(self):  
        return self.name

    @property
    def total_text_tag_count(self):
        return sum([tagger.total_text_tag_count for tagger in self.taggers.all()])
    
    @property
    def total_valid_text_tag_count(self):
        return sum([tagger.total_valid_text_tag_count for tagger in self.taggers.all()])
    
    @property
    def number_of_tags(self):
        return self.tags.count()

    @property
    def number_of_taggers(self):
        return self.taggers.count()

    # def add_to_unknown_tag_examples(self, token_content):
    #     examples = self.unknown_tag['examples']
    #     if (token_content not in examples 
    #             and len(examples) < 15 ):
    #         self.unknown_tag['examples'].append(token_content)
    #         self.save(update_fields=['unknown_tag']) 

    class Meta:
        verbose_name = 'Tag Set'
        verbose_name_plural = 'Tag Sets'
        ordering = ('-created',)

class Token(models.Model):
    logger = logging.getLogger(__name__)
    created = models.DateTimeField(auto_now_add=True)
    content = models.CharField(max_length=200, unique=True)
    tags = models.ManyToManyField('Tag', through='TokenTag', related_name='tokens', 
                            related_query_name='token', blank=True,)

    class Meta:
        verbose_name = 'Token'
        verbose_name_plural = 'Tokens'
        ordering = ('-created',)

    @property
    def number_of_tags(self):
        return self.tags.count()

    def __str__(self):  
        return self.content

class Tag(models.Model):
    logger = logging.getLogger(__name__)
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=15)
    persian = models.CharField(max_length=30)
    color = ColorField()
    tag_set = models.ForeignKey(to='TagSet', on_delete=models.CASCADE, related_name='tags', related_query_name='tag')
    # examples = ArrayField(models.CharField(max_length=50), blank=True, default=list)

    def __str__(self):  
        return self.name

    class Meta:
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
        ordering = ('-created',)
        unique_together = (("name", "tag_set"), ("persian", "tag_set"),)

    # @property
    # def update_examples(self, text_tag_tagged_tokens_list):
    #     examples = set()
    #     # search_token = [{'tag': {'name': self.name, 'persian': self.persian, 'color': self.color }}]
    #     # text_tag_tokens_list = TextTag.objects.filter(tagger__tag_set=self.tag_set, is_valid=True, \
    #     #     tokens__contains=search_token).values_list('tagged_tokens', flat=True)

    #     # self.logger.debug(f'> {self.name} text_tag_tokens_list.count() : {text_tag_tokens_list.count()} {type(text_tag_tokens_list)}')

    #     # if not text_tag_tokens_list or text_tag_tokens_list.count() == 0:
    #     #     self.examples = list(examples)

    #     # text_tag_tokens_list = list(text_tag_tokens_list)
        
    #     # text_tag_tokens_list = random.sample(text_tag_tokens_list, min(len(text_tag_tokens_list), 40))
        
    #     self.logger.debug(f'> {self.name} len(text_tag_tokens_list) : {len(text_tag_tokens_list)} {type(text_tag_tokens_list)}')
    #     for text_tag_tagged_tokens in text_tag_tagged_tokens_list:
    #         # self.logger.debug(f'> text_tag_tagged_tokens[0] != self.tag_set.name => {text_tag_tagged_tokens[0]} != {self.tag_set.name} => {text_tag_tagged_tokens[0] != self.tag_set.name}')
    #         if text_tag_tagged_tokens[0] != self.tag_set.name:
    #             continue
    #         for text_tag_tagged_token in text_tag_tagged_tokens[1]:
    #             if text_tag_tagged_token['tag']['name'] == self.name:
    #                 examples.add(text_tag_tagged_token['token'])
    #                 if len(examples) >= 50:
    #                     break

    #     self.examples = list(examples)
    #     self.save(update_fields=['examples']) 

    @property
    def number_of_tokens(self):
        return self.tokens.count()

    @property
    def percentage(self):
        all_tags = Tag.objects.filter(tag_set=self.tag_set)
        all_tokens_count = sum([tag.tokens.count() for tag in all_tags])
        return round((self.tokens.count() / all_tokens_count) * 100, 3)

class TokenTag(models.Model):
    logger = logging.getLogger(__name__)
    created = models.DateTimeField(auto_now_add=True)
    token = models.ForeignKey('Token', on_delete=models.CASCADE, related_name='token_tags', related_query_name='token_tag')
    tag = models.ForeignKey('Tag', on_delete=models.CASCADE, related_name='token_tags', related_query_name='token_tag')
    number_of_repetitions = models.IntegerField(blank=True, default=0)

    class Meta:
        verbose_name = 'Token Tag'
        verbose_name_plural = 'Token Tags'
        ordering = ('-created',)
        unique_together = (("token", "tag"),)

    # @property
    # def number_of_repetitions(self):
    #     count = 0
    #     return cache.tag_set_token_tags[self.tag.tag_set.name][self.token.content][self.tag.name]
        # text_tag_tagged_tokens_list = TextTag.objects.filter(
        #     is_valid=True, 
        #     tagger__tag_set=self.tag.tag_set
        # ).values_list('tagged_tokens', flat=True)
        # for text_tag_tagged_tokens in text_tag_tagged_tokens_list:
        #     for tagged_token in text_tag_tagged_tokens:
        #         if (tagged_token['token'] == self.token.content and
        #             tagged_token['tag']['name'] == self.tag.name):
        #             count += 1
        # return count
        # self.save(update_fields=['number_of_repetitions'])


class Validator(models.Model):
    logger = logging.getLogger(__name__)
    name = models.SlugField(default='unknown-validator', unique=True)
    show_name = models.CharField(max_length=200, default='اعتبارسنج نامشخص')
    created = models.DateTimeField(auto_now_add=True)
    owner = models.CharField(max_length=100, default='undefined')

    class Meta:
        verbose_name = 'Validator'
        verbose_name_plural = 'Validators'
        ordering = ('-created',)
    
    def __str__(self):
        return  self.name

    @property
    def total_text_normal_count(self):
        return self.text_normals.count()

    @property
    def total_word_normal_count(self):
        return self.word_normals.count()

    @property
    def total_text_tag_count(self):
        return self.text_tags.count()


class Normalizer(models.Model):
    logger = logging.getLogger(__name__)
    name = models.SlugField(default='unknown-normalizer', unique=True)
    show_name = models.CharField(max_length=200, default='نرمال‌کننده نامشخص')
    created = models.DateTimeField(auto_now_add=True)
    owner = models.CharField(max_length=100, default='undefined')
    is_automatic = models.BooleanField(default=False)
    model_details = UTF8JSONField(default=dict, blank=True) # contains model training details
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Normalizer'
        verbose_name_plural = 'Normalizers'
        ordering = ('created',)

    def __str__(self):  
        return self.name

    @property
    def total_text_normal_count(self):
        return self.text_normals.count()

    @property
    def total_valid_text_normal_count(self):
        return self.text_normals.filter(is_valid=True).count()

    @property
    def total_word_normal_count(self):
        return self.word_normals.count()

    @property
    def total_valid_word_normal_count(self):
        return self.word_normals.filter(is_valid=True).count()


    def train(self):
        pass

    def normalize(self, text):
        text_normal_content = text.content
        text_normal, created = TextNormal.objects.update_or_create(
            normalizer=self, text=text,
            defaults={'content':text_normal_content},
        )
        self.logger.debug(f"> created : {created}")
        return text_normal

class Tagger(models.Model):
    logger = logging.getLogger(__name__)
    name = models.SlugField(default='unknown-tagger', unique=True)
    show_name = models.CharField(max_length=200, default='برچسب‌زن نامشخص')
    created = models.DateTimeField(auto_now_add=True)
    owner = models.CharField(max_length=100, default='undefined')
    is_automatic = models.BooleanField(default=False)
    model_details = UTF8JSONField(default=dict, blank=True) # contains model training details
    tag_set = models.ForeignKey(to=TagSet, on_delete=models.DO_NOTHING, related_name='taggers', related_query_name='tagger')
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tagger'
        verbose_name_plural = 'Taggers'
        ordering = ('created',)
    
    def __str__(self):  
        return self.name

    @property
    def total_text_tag_count(self):
        return self.text_tags.count()
    
    @property
    def total_valid_text_tag_count(self):
        return self.text_tags.filter(is_valid=True).count()
    
    def train(self):
        pass

    def tag(self, text):
        pass


"""
from mohaverekhan.models import Text, Sentence, Tag, Token
from mohaverekhan.serializers import TextSerializer, SentenceSerializer, TokenSerializer, TagSerializer
text = Text.objects.create(content="سلام. چطوری خوبی؟")
serializer = TextSerializer(text)
serializer.data
sentence1 = Sentence.objects.create(content="سلام.")
serializer = SentenceSerializer(sentence1)
serializer.data
text.sentences.add(sentence1)
serializer = TextSerializer(text)
serializer.data

from mohaverekhan.models import Text, Sentence, Tag, Token
from mohaverekhan.serializers import TextSerializer, SentenceSerializer, TokenSerializer, TagSerializer
text = Text.objects.create(content="سلام. چطوری خوبی؟")
serializer = TextSerializer(text)
serializer.data
sentence1 = Sentence.objects.create(content="سلام.")
serializer = SentenceSerializer(sentence1)
serializer.data
text.sentences = sentence1
text.save()
serializer = TextSerializer(text)
serializer.data


from mohaverekhan.models import Text, Sentence, Tag, Token
from mohaverekhan.serializers import TextSerializer, SentenceSerializer, TokenSerializer, TagSerializer
text = Text(content="سلام. چطوری خوبی؟")
text.save()
serializer = TextSerializer(text)
serializer.data
sentence1 = Sentence(content="سلام.")
sentence1.save()
serializer = SentenceSerializer(sentence1)
serializer.data
text.sentences.add(sentence1)
serializer = TextSerializer(text)
serializer.data


sentence2 = Sentence.objects.create(text=text, content="چطوری خوبی؟")
tag1 = Tag.objects.create(name="V")
tag2 = Tag.objects.create(name="N")
tag3 = Tag.objects.create(name="E")
token1 = Token.objects.create(sentence=sentence1, content="سلام", tag=tag1)
token1


text = Text.objects.get(pk=1)
text
"""


"""
E : ['با', 'در', 'به', 'از', 'برای', 'علیرغم', 'جز', 'در مقابل', 'پس از', 'تا', 'بر', 'به دنبال', 'از نظر', 'جهت', 'در پی', 'میان', 'به عنوان', 'تحت', 'از طریق', 'به دست', 'بر اساس', 'در جهت', 'از سوی', 'در زمینه', 'زیر', 'در معرض', 'به جای', 'وارد', 'از جمله', 'درباره', 'بدون', 'فرا', 'به صورت', 'به خاطر', 'پیرامون', 'در مورد', 'طی', 'روی', 'قبل از', 'توسط', 'بعد', 'مقابل', 'از روی', 'در حضور', 'به رغم', 'به دلیل', 'برابر', 'در برابر', 'با توجه به', 'به نفع']
Noun - اسم - N : ['قدرت', 'یهودیها', 'انگلیس', 'وجود', 'فضای', 'سو', 'مطبوعات', 'کشور', 'نیاز', 'منابع', 'چیز', 'رشد', 'رویتر', 'فراهم', 'موقعیتی', 'سال', 'جلیوس', 'دفتر', 'نزدیکی', 'بازار', 'بورس', 'لندن', 'گشایش', 'عده', 'یهودیهای', 'آلمان', 'دعوت', 'کار', 'عهده', 'بازاریابی', 'معرفی', 'خبرگزاری', 'پترزبورگ', 'سفر', 'نامه ای', 'نیکولای', 'گریش', 'سردبیران', 'نشریات', 'جائی', 'سردبیر', 'درک', 'پل', 'استوف', 'استقبال', 'قراردادی', 'مبلغ', 'روبل', 'امضاء', 'خدمات']
Verb - فعل - V : ['گرفتن', 'آمدن', 'شدن', 'شده', 'بود', 'کرد', 'شدند', 'گرفتند', 'نوشت', 'نداشت', 'رساند', 'دهد', 'آورده', 'نبودند', 'می توانست', 'باشد', 'است', 'بودن', 'گردید', 'آوردند', 'یافت', 'توانسته', 'کند', 'نمی توانست', 'شود', 'بودند', 'بردن', 'نمود', 'کردند', 'می شد', 'می داشت', 'نیاورد', 'زدند', 'می کردند', 'داشت', 'کنند', 'آمد', 'بست', 'کردن', 'رفت', 'می کرد', 'گرفته', 'دادن', 'کندن', 'شد', 'افتاد', 'می گریختند', 'نمی شناختند', 'ریخت', 'آمدند']
J : ['و', 'از سوی دیگر', 'که', 'هم', 'درعین حال', 'اگر', 'لذا', 'ولی', 'هرچند', 'نیز', 'سپس', 'درحالیکه', 'چون', 'تا', 'هم چنین', 'اما', 'وقتی', 'یا', 'هنگامی که', 'تاآنجاکه', 'درحالی که', 'چراکه', 'چنانچه', 'در حالی که', 'همچنین', 'چنانکه', 'گرچه', 'به طوری که', 'به این ترتیب', 'نه فقط', 'بلکه', 'بنابراین', 'از آنجا که', 'ضمناً', 'اگرچه', 'نه تنها', 'زیرا', 'همانطورکه', 'در صورتی که', 'پس', 'باآنکه', 'به طوریکه', 'بدین ترتیب', 'یعنی', 'چنان که', 'چه', 'ولو', 'از این رو', 'آنگاه', 'علاوه برآنکه']
Adjective - صفت - A : ['مناسب', 'آزاد', 'خبری', 'سریع', 'دایر', 'زیادی', 'دقیقی', 'محلی', 'موظف', 'مرتب', 'ملموسی', 'مختلف', 'حاضر', 'معتبر', 'مجبور', 'فراوان', 'کمتر', 'تلگرافی', 'داخلی', 'جدید', 'مهمترین', 'مالی', 'دولتی', 'معتقد', 'موفق', 'بیشتر', 'مطبوعاتی', 'انحصاری', 'معترض', 'پیشتاز', 'رقیب', 'پیشرفته تر', 'مربوط', 'بالا', 'شایانی', 'خارجی', 'حساس', 'بحرانی', 'مستقر', 'سراسری', 'منعقد', 'مستحکمتر', 'شرقی', 'رایگان', 'سلطنتی', 'سفید', 'گروهی', 'نهایی', 'جالب', 'بزرگ']
Number - عدد - U : ['یک', '1857', 'اولین', 'یکی', '3000', '8', '1863', '1868', '9', '1887', '1890', '10', 'دو', '11', 'چهارمین', '1872', '1906', '12', 'بیستم', 'شصت', 'نخستین', 'بیست', 'میلیارد', 'هزاران', 'پنج', 'هزار', 'آخر', 'هفتاد', '1953', '21', '1962', 'چهار', '1988', '1989', 'آخرین', 'اول', '1984', 'سی', '1917', 'شش', 'چهارم', '1998', '7', '78', '53', 'تک', '3', '15', '75', '66']
T : ['این', 'همه', 'یکی', 'آن', 'بعضی', 'تعدادی', 'چند', 'هیچیک', 'هر', 'بیشتر', 'بسیاری', 'چندین', 'بیش', 'تمام', 'تمامی', 'هیچ', 'همین', 'چه', 'همان', 'کدام', 'برخی', 'اکثر', 'بخشی', 'عده ای', 'نیمی', 'کلیه', 'غالب', 'حداقل', 'جمعی', 'پاره ای', 'فلان', 'همهٌ', 'اکثریت', 'کل', 'همگی', 'مقداری', 'قسمتی', 'شمار', 'اغلب', 'اینگونه', 'حداکثر', 'جمله', 'همه ی', 'عموم', 'شماری', 'تجمعی', 'همانجا', 'کلیهٌ', 'کمی', 'خیلی']
Pronoun - ضمیر - Z : ['آنها', 'دیگر', 'خود', 'این', 'آن', 'دیگری', 'آن ها', 'او', 'آنهایی', 'همه', 'من', 'این ها', 'آنان', 'هم', 'وی', 'یکدیگر', 'آنانی', 'همین', 'آنچه', 'ایشان', 'همگی', 'غیره', 'اینان', 'تو', 'کی', 'بسیاری', 'چنین', 'همگان', 'خویش', 'ما', 'دیگران', 'چی', 'بعضیها', 'برخی ها', 'جنابعالی', 'شما', 'چنان', 'همان', 'اینها', 'خویشتن', 'بعضی', 'این چنین', 'حضرتعالی', 'برخی', 'جملگی', 'فلانی', 'ماها', 'همدیگر', 'اینی', 'پاره ای']
Sign - علائم - O : ['،', '.', '»', '«', '#', ':', '...', '؟', '_', 'ـ', '-', '/', ')', '(', '!', '؛', '"', '+', '*', ',', '$', '…', 'ْ', '@', '[', ']', '}', '{']
L : ['چنین', 'قبضه', 'گونه', 'تنها', 'رشته', 'قبیل', 'سلسله', 'تعداد', 'جفت', 'نوع', 'چنان', 'دستگاه', 'نفرساعت', 'مورد', 'نفر', 'سری', 'تن', 'فقره', 'هکتار', 'جمله', 'درصد', 'کیلوگرم', 'بسی', 'کیلو', 'فروند', 'میزان', 'لیتر', 'بسته', 'جلد', 'لیر', 'تخته', 'ریزه', 'گرم', 'بشکه', 'مترمربع', 'کیلومتر', 'میکروگرم', 'قلم', 'مقدار', 'لیره', 'قطعه', 'واحد', 'متر', 'نمونه', 'دست', 'ریشتر', 'عدد', 'نخ', 'لیوان', 'تا']
Postposition - حرف اضافه پسین - P : ['را', 'رو']
Adverb - قید - D : ['به گرمی', 'از آن پس', 'به موقع', 'هنوز', 'قطعا', 'باز', 'شدیدا', 'مثل', 'صریحا', 'عمدتا', 'بطورکلی', 'چون', 'ابتدا', 'در مقابل', 'البته', 'بعد', 'درحقیقت', 'دیگر', 'بهتر', 'بارها', 'مانند', 'اکنون', 'اینک', 'کاملاً', 'چگونه', 'به زور', 'حتی', 'مبادا', 'همزمان', 'بعداً', 'به سرعت', 'نه', 'بویژه', 'نظیر', 'قبلاً', 'قاچاقی', 'عمدتاً', 'بسیار', 'واقعاً', 'فقط', 'کنار', 'به ویژه', 'بندرت', 'مسلماً', 'مطمئناً', 'دوباره', 'کم وبیش', 'به طور قطع', 'در حال حاضر', 'به ترتیب']
C : ['ش', 'یشان', 'شان', 'م', 'ام', 'یش', 'اش', 'ست', 'ند', 'اند', 'ب', 'دین', 'ت', 'ک', 'ستی', 'یم', 'مان', 'ید', 'دان', 'یتان', 'تان', 'ا', 'یند', 'ات', 'یت', 'ی', 'ه', 'یمان', 'اید', 'یی', 'ز', 'ایم', 'ییم', 'ین', 'دانان', 'ستند', 'ئی', 'ستم', 'و', 'ای', 'ر', 'دانچه', 'دو', 'چ', 'هات', 'تون', 'شون', 'س', 'یه', 'هام']
R : ['سالگی', 'ساله', 'الف', 'د', '!!!', 'G . I . S', 'کیلومتری', 'روزه', 'نه', 'آری', 'ردوا', 'الحجر', 'من', 'حیث', 'جاء', 'فان', 'الشر', 'لا', 'یدفعه', 'الا', 'بسمه تعالی', 'ساله ای', 'APB', 'ماهه', 'نفره', 'سلام', 'پوندی', 'STAINLESS', 'STEEL', 'AWTE', 'تنی', 'میلیونی', 'صفحه ای', 'یا', 'صــاح', 'للعجـب', 'دعــوتک', 'ثـم', 'لـم', 'تجـب', 'الی', 'القینات', 'والشهوات', 'والصهبــاء', 'و', 'الطـــرب', 'باطیه', 'مکلله', 'علیهــا', 'سـاده']
Interjection - حرف ندا - حرف ربط - I : ['ای', 'یا', 'زهی', 'هان', 'الا', 'آی', 'ایها', 'آهای'] 
"""

"""""
حرف اضافه
حرف ربط
قید مقدار
واحد
"""
##حرف اضافه