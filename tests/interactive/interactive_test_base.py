from __future__ import absolute_import, print_function
from builtins import zip
from builtins import input

import array
import os
import pytest
import shutil
import warnings

import pyglet
from pyglet.image import get_buffer_manager

from ..base import PygletTestCase

try:
    # If the easygui package is available, use it to display popup questions, instead of using the
    # console (which might lose focus to the Pyglet windows).
    # Not using Pyglet to show a window with the question to prevent interfering with the test.
    import easygui
    _has_gui = True
except:
    _has_gui = False

local_dir = os.path.dirname(__file__)

base_screenshot_path = os.path.join(local_dir, 'screenshots')
committed_screenshot_path = os.path.join(base_screenshot_path, 'committed')
session_screenshot_path = os.path.join(base_screenshot_path, 'session')

del local_dir


class InteractiveTestCase(PygletTestCase):
    """
    Base class for interactive tests.

    Interactive tests exist on several levels of interactivity. The least interactive tests store
    screenshots of user validated output that can be used to automatically compare to in a non
    interactive run. More interactive tests cannot validate the results automatically, but can
    run fully automatic for sanity checks. Finally there are tests that really require the user
    to perform an action for the test to continue.

    Use the decorators @only_interactive, @requires_user_validation and @requires_user_action to
    mark a test case as such. This only works on the test suite (class) level.
    """
    # Show interactive prompts
    interactive = True

    # Allow tests missing reference screenshots to pass
    allow_missing_screenshots = False

    def __init__(self, methodName):
        super(InteractiveTestCase, self).__init__(methodName=methodName)
        self._screenshots = []

    def check_screenshots(self):
        # If we arrive here, there have not been any failures yet
        if self.interactive:
            self._commit_screenshots()
        else:
            if self._has_reference_screenshots():
                self._validate_screenshots()
                # Always commit the screenshots here. They can be used for the next test run.
                # If reference screenshots were already present and there was a mismatch, it should
                # have failed above.
                self._commit_screenshots()

            elif self.allow_missing_screenshots:
                warnings.warn('No committed reference screenshots available. Ignoring.')
            else:
                self.fail('No committed reference screenshots available. Run interactive first.')

    def user_verify(self, description, take_screenshot=True):
        """
        Request the user to verify the current display is correct.
        """
        failed = False
        failure_description = None

        if self.interactive:
            failure_description = _ask_user_to_verify(description)
        if take_screenshot:
            self._take_screenshot()

        if failure_description is not None:
            self.fail(failure_description)

    def assert_image_equal(self, a, b, tolerance=0, msg=None):
        if msg is None:
            msg = 'Screenshot does not match last committed screenshot'
        if a is None:
            self.assertIsNone(b, msg)
        else:
            self.assertIsNotNone(b, msg)

        a_data = a.image_data
        b_data = b.image_data

        self.assertEqual(a_data.width, b_data.width, msg)
        self.assertEqual(a_data.height, b_data.height, msg)
        self.assertEqual(a_data.format, b_data.format, msg)
        self.assertEqual(a_data.pitch, b_data.pitch, msg)
        self.assert_buffer_equal(a_data.data, b_data.data, tolerance, msg)

    def assert_buffer_equal(self, a, b, tolerance=0, msg=None):
        if tolerance == 0:
            self.assertEqual(a, b, msg)

        self.assertEqual(len(a), len(b), msg)

        a = array.array('B', a)
        b = array.array('B', b)
        for (aa, bb) in zip(a, b):
            self.assertTrue(abs(aa - bb) <= tolerance, msg)

    def _take_screenshot(self):
        """
        Take a screenshot to allow visual verification.
        """
        screenshot_name = self._get_next_screenshot_name()
        screenshot_file_name = self._get_screenshot_session_file_name(screenshot_name)

        get_buffer_manager().get_color_buffer().image_data.save(screenshot_file_name)

        self._screenshots.append(screenshot_name)

    def _commit_screenshots(self):
        """
        Store the screenshots for reference if the test case is successful.
        """
        for screenshot_name in self._screenshots:
            shutil.copyfile(self._get_screenshot_session_file_name(screenshot_name),
                            self._get_screenshot_committed_file_name(screenshot_name))

    def _validate_screenshots(self):
        """
        Check the screenshot against regression reference images if available.
        """
        for screenshot_name in self._screenshots:
            committed_image = pyglet.image.load(self._get_screenshot_committed_file_name(screenshot_name))
            session_image = pyglet.image.load(self._get_screenshot_session_file_name(screenshot_name))
            self.assert_image_equal(committed_image, session_image)

    def _has_reference_screenshots(self):
        """
        Check whether there are screenshots from a previous successful run available to validate
        against. Use after taking all required screenshots. Also validates the number of required
        screenshots.
        """
        for screenshot_name in self._screenshots:
            if not os.path.isfile(self._get_screenshot_committed_file_name(screenshot_name)):
                return False
        else:
            return True

    def _get_next_screenshot_name(self):
        """
        Get the unique name for the next screenshot.
        """
        return '{}.{}.{}.{:03d}.png'.format(self.__class__.__module__,
                                        self.__class__.__name__,
                                        self._testMethodName,
                                        len(self._screenshots)+1)

    def _get_screenshot_session_file_name(self, screenshot_name):
        return os.path.join(session_screenshot_path, screenshot_name)

    def _get_screenshot_committed_file_name(self, screenshot_name):
        return os.path.join(committed_screenshot_path, screenshot_name)

if _has_gui:
    def _ask_user_to_verify(description):
        failure_description = None
        success = easygui.ynbox(description)
        if not success:
            failure_description = easygui.enterbox('Enter failure description:')
        return failure_description
else:
    def _ask_user_to_verify(description):
        failure_description = None
        print()
        print(description)
        while True:
            response = input('Passed [Yn]: ')
            if not response:
                break
            elif response in 'Nn':
                failure_description = input('Enter failure description: ')
                break
            elif response in 'Yy':
                break
            else:
                print('Invalid response')
        return failure_description


def only_interactive(cls):
    """
    Mark a test case (class) as only interactive. This means it will be skipped if the user requests
    to run noninteractively.
    """
    return pytest.mark.only_interactive(cls)

def requires_user_action(cls):
    """
    Mark a test case (class) as requiring user action to run. The test cannot be run non interactive
    at all.
    """
    return pytest.mark.requires_user_action(cls)

def requires_user_validation(cls):
    """
    Mark a test case (class) as requiring the user to validate the outcome. It cannot use screenshot
    comparison or other asserts to validate. It is however possible to run non interactively to
    perform a simple sanity check (no exceptions/crashes).
    """
    return pytest.mark.requires_user_validation(cls)
