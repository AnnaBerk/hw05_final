import shutil
import tempfile

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.conf import settings
from http import HTTPStatus

from ..models import Post, Group, Comment

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)

User = get_user_model()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostCreateFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='group',
            description='Тестовое описание',
            slug='slug',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост больше 15 симовлов',
            group=cls.group,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def obj_counter_redirect(obj, count_arg):
        """Проверяет добавился ли пост и сработал редирект"""
        def decorator(func):
            def wrapper(self):
                countob = obj.objects.count()
                response, path = func(self)
                self.assertRedirects(response, path)
                self.assertEqual(obj.objects.count(), countob + count_arg)
            return wrapper
        return decorator

    @obj_counter_redirect(Post, 1)
    def test_can_create_post(self):
        """Авторизированный пользователь может создавать пост"""
        data = {
            'text': 'Текст из формы',
            'group.title': 'group',
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=data,
            follow=True,
        )
        path = reverse('posts:profile', kwargs={'username': 'auth'})
        self.assertTrue(
            Post.objects.filter(
                text='Текст из формы',
            ).exists()
        )
        return [response, path]

    @obj_counter_redirect(Post, 0)
    def test_can_edit_post(self):
        """Авторизированный пользователь может редактировать пост"""
        form_data = {
            'text': 'Текст из формы',
        }
        response = self.authorized_client.post(
            reverse('posts:post_edit', kwargs={'post_id': '1'}),
            data=form_data,
            follow=True,
        )
        path = reverse(
            'posts:post_detail', kwargs={'post_id': '1'})
        new_post = Post.objects.get(id='1')
        self.assertEqual(new_post.id, self.post.id)
        self.assertNotEqual(new_post.text, self.post.text)
        return [response, path]

    @obj_counter_redirect(Post, 0)
    def test_cant_create_post(self):
        """Неавторизированный пользователь не может создавать пост"""
        form_data = {
            'text': 'Текст из формы',
            'group.title': 'group',
        }
        response = self.guest_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True,
        )
        return [response, '/auth/login/?next=/create/']

    @obj_counter_redirect(Post, 1)
    def test_can_create_post_with_img(self):
        """Пост с картинкой добавляется в бд"""
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif',
        )
        form_data = {
            'text': 'Текст',
            'image': uploaded,
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True,
        )
        path = reverse(
            'posts:profile', kwargs={'username': 'auth'})
        self.assertTrue(
            Post.objects.filter(
                text='Текст',
                image='posts/small.gif',
            ).exists()
        )
        return [response, path]

    @obj_counter_redirect(Comment, 1)
    def test_can_create_comment(self):
        """Авторизированный пользователь может комментировать"""
        form_data = {
            'text': 'Текст комментария',
        }
        response = self.authorized_client.post(
            reverse('posts:add_comment', kwargs={'post_id': '1'}),
            data=form_data,
            follow=True,
        )
        path = reverse(
            'posts:post_detail', kwargs={'post_id': '1'})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(
            Comment.objects.filter(
                text='Текст комментария',
            ).exists()
        )
        return [response, path]

    @obj_counter_redirect(Comment, 0)
    def test_cant_create_comment(self):
        """Неавторизированный пользователь не может комментировать"""
        form_data = {
            'text': 'Текст комментария',
        }
        response = self.guest_client.post(
            reverse('posts:add_comment', kwargs={'post_id': '1'}),
            data=form_data,
            follow=True,
        )
        return [response, '/auth/login/?next=/posts/1/comment/']
