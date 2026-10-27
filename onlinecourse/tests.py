from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.contrib.auth.models import User
from .models import Course, Lesson, Question, Choice, Submission, Enrollment
from . import views


class OnlineCourseModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teststudent', password='testpassword123')
        self.course = Course.objects.create(name='Cloud App Development', description='Learn Django and Cloud')
        self.enrollment = Enrollment.objects.create(user=self.user, course=self.course, mode='honor')

        # Question 1: single correct choice
        self.q1 = Question.objects.create(course=self.course, question_text='What is Django?', grade=10)
        self.c1_1 = Choice.objects.create(question=self.q1, choice_text='A Python web framework', is_correct=True)
        self.c1_2 = Choice.objects.create(question=self.q1, choice_text='A database engine', is_correct=False)

        # Question 2: multiple correct choices
        self.q2 = Question.objects.create(course=self.course, question_text='Which are Python data types?', grade=20)
        self.c2_1 = Choice.objects.create(question=self.q2, choice_text='list', is_correct=True)
        self.c2_2 = Choice.objects.create(question=self.q2, choice_text='dict', is_correct=True)
        self.c2_3 = Choice.objects.create(question=self.q2, choice_text='varchar', is_correct=False)

    def test_model_str_methods(self):
        self.assertEqual(str(self.q1), 'Question: What is Django?')
        self.assertEqual(str(self.c1_1), 'Choice: A Python web framework')
        submission = Submission.objects.create(enrollment=self.enrollment)
        self.assertIn('Submission', str(submission))
        self.assertIn('teststudent', str(submission))

    def test_question_default_grade(self):
        q = Question.objects.create(course=self.course, question_text='Default grade question?')
        self.assertEqual(q.grade, 1)

    def test_is_get_score_single_choice(self):
        # Correct answer
        self.assertTrue(self.q1.is_get_score([self.c1_1.id]))
        # Wrong answer
        self.assertFalse(self.q1.is_get_score([self.c1_2.id]))
        # Empty selection
        self.assertFalse(self.q1.is_get_score([]))
        # Both selected (includes incorrect)
        self.assertFalse(self.q1.is_get_score([self.c1_1.id, self.c1_2.id]))

    def test_is_get_score_multiple_choices(self):
        # All correct selected
        self.assertTrue(self.q2.is_get_score([self.c2_1.id, self.c2_2.id]))
        # Only partial correct selected
        self.assertFalse(self.q2.is_get_score([self.c2_1.id]))
        # Correct plus incorrect selected
        self.assertFalse(self.q2.is_get_score([self.c2_1.id, self.c2_2.id, self.c2_3.id]))


class OnlineCourseURLAndViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='examuser', password='password123')
        self.course = Course.objects.create(name='Django Advanced', description='Deep dive')
        self.enrollment = Enrollment.objects.create(user=self.user, course=self.course, mode='honor')

        self.q1 = Question.objects.create(course=self.course, question_text='Is Django MVC/MVT?', grade=50)
        self.c1 = Choice.objects.create(question=self.q1, choice_text='Yes, MVT', is_correct=True)
        self.c2 = Choice.objects.create(question=self.q1, choice_text='No', is_correct=False)

    def test_url_reverse_and_resolve(self):
        # Submit route
        submit_url = reverse('onlinecourse:submit', args=[self.course.id])
        self.assertEqual(submit_url, f'/onlinecourse/{self.course.id}/submit/')
        resolved_submit = resolve(submit_url)
        self.assertEqual(resolved_submit.func, views.submit)

        # Show exam result route
        result_url = reverse('onlinecourse:show_exam_result', args=[self.course.id, 1])
        self.assertEqual(result_url, f'/onlinecourse/course/{self.course.id}/submission/1/result/')
        resolved_result = resolve(result_url)
        self.assertEqual(resolved_result.func, views.show_exam_result)

    def test_course_details_template_used(self):
        response = self.client.get(reverse('onlinecourse:course_details', args=[self.course.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'onlinecourse/course_details_bootstrap.html')

    def test_submit_and_show_exam_result_flow(self):
        self.client.login(username='examuser', password='password123')

        # Submit POST with choice
        submit_url = reverse('onlinecourse:submit', args=[self.course.id])
        post_data = {
            f'choice_{self.c1.id}': self.c1.id
        }
        response = self.client.post(submit_url, data=post_data)
        self.assertEqual(response.status_code, 302)

        # Verify Submission created
        submission = Submission.objects.filter(enrollment=self.enrollment).first()
        self.assertIsNotNone(submission)
        self.assertIn(self.c1, submission.choices.all())

        # Check result page
        result_url = reverse('onlinecourse:show_exam_result', args=[self.course.id, submission.id])
        res_page = self.client.get(result_url)
        self.assertEqual(res_page.status_code, 200)
        self.assertTemplateUsed(res_page, 'onlinecourse/exam_result_bootstrap.html')

        # Context checks
        self.assertEqual(res_page.context['grade'], 50)
        self.assertEqual(res_page.context['possible'], 50)
        self.assertEqual(res_page.context['selected_ids'], [self.c1.id])
        self.assertContains(res_page, 'Exam results')
        self.assertContains(res_page, 'Is Django MVC/MVT?')
        self.assertContains(res_page, 'Correct answer:')
